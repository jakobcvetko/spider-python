"""avto.net progressive-scrape pipeline (mirrors bolha_common)."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
from sqlalchemy import delete, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models import (
    AvtonetAd,
    AvtonetAdProbe,
    AvtonetAdState,
    AvtonetScrapeMeta,
)
from app.models.avtonet_ad import (
    AD_STATUS_PENDING,
    AD_STATUS_REMOVED,
    AD_STATUS_SUCCESS,
    SCRAPE_RESULT_EMPTY,
    SCRAPE_RESULT_ERROR,
    SCRAPE_RESULT_REMOVED,
    SCRAPE_RESULT_SUCCESS,
)
from app.scraper_events import make_event
from scraper.sources.avto_net_common import (
    LISTING_SOURCE,
    LOOKAHEAD_ADS,
    SCOUT_HTTP_RETRIES,
)
from scraper.sources.avto_net_probe import ProbeResult, probe_ad_id as fetch_probe

log = logging.getLogger(__name__)

EmitFn = Callable[[dict[str, Any]], Awaitable[None]] | None

PipelineKind = Literal["active", "not_yet_created", "expired", "not_found", "bad_status"]

STATUS_LOOKAHEAD = "lookahead"
STATUS_PENDING_FALLBACK = "pending_fallback"
STATUS_FALLBACK_WARMING = "fallback_warming"
STATUS_TIMED_OUT = "timed_out"
STATUS_EXPIRED = "expired"

LOOKAHEAD_TIMEOUT_SECONDS = 5.0
LOOKAHEAD_HIGH_WATER_REFRESH_BATCHES = 50
FALLBACK_CYCLE_PAUSE_SECONDS = 10
FALLBACK_TIMEOUT_SECONDS = 300
MAX_FALLBACK_IDS_PER_FETCH = 40


def pipeline_kind_from_probe(result: ProbeResult) -> PipelineKind:
    if result.kind == "active":
        return "active"
    if result.kind == "redirect":
        return "expired"
    if result.kind in ("not_found", "unknown"):
        return "not_yet_created"
    if result.kind == "http_error":
        return "bad_status"
    return "bad_status"


def outcome_from_class(kind: PipelineKind) -> str:
    return {
        "active": "active",
        "not_yet_created": "not_yet_created",
        "expired": "expired",
        "not_found": "not_found",
        "bad_status": "bad_http_status",
    }[kind]


def is_known_probe_kind(kind: PipelineKind) -> bool:
    return kind in ("active", "expired")


def scrape_result_from_outcome(outcome: str) -> str:
    if outcome == "active":
        return SCRAPE_RESULT_SUCCESS
    if outcome == "expired":
        return SCRAPE_RESULT_REMOVED
    if outcome == "not_yet_created":
        return SCRAPE_RESULT_EMPTY
    return SCRAPE_RESULT_ERROR


def ad_status_from_scrape_result(result: str) -> str:
    if result == SCRAPE_RESULT_SUCCESS:
        return AD_STATUS_SUCCESS
    if result == SCRAPE_RESULT_REMOVED:
        return AD_STATUS_REMOVED
    return AD_STATUS_PENDING


def merge_ad_status(current: str, new: str) -> str:
    rank = {AD_STATUS_PENDING: 0, AD_STATUS_REMOVED: 1, AD_STATUS_SUCCESS: 2}
    if rank.get(new, 0) > rank.get(current, 0):
        return new
    return current


async def get_meta(db: AsyncSession) -> AvtonetScrapeMeta:
    row = await db.get(AvtonetScrapeMeta, 1)
    if row is None:
        row = AvtonetScrapeMeta(id=1)
        db.add(row)
        await db.flush()
    return row


async def meta_begin_fetch(db: AsyncSession, *, high: int) -> None:
    now = datetime.now(timezone.utc)
    await db.execute(
        update(AvtonetScrapeMeta)
        .where(AvtonetScrapeMeta.id == 1)
        .values(
            last_fetch_high_water=high,
            last_fetch_started_at=now,
            last_batch_started_at=now,
        )
    )
    await db.flush()


async def meta_set_last_working(db: AsyncSession, ad_id: int) -> None:
    now = datetime.now(timezone.utc)
    await db.execute(
        update(AvtonetScrapeMeta)
        .where(AvtonetScrapeMeta.id == 1)
        .values(last_working_ad_id=ad_id, last_working_at=now)
    )
    await db.flush()


async def max_numeric_listing_id(db: AsyncSession) -> int:
    r = await db.execute(
        text(
            """
            SELECT MAX(CAST(external_id AS BIGINT))
            FROM listings
            WHERE source = :src AND external_id ~ '^[0-9]+$'
            """
        ),
        {"src": LISTING_SOURCE},
    )
    v = r.scalar_one_or_none()
    return int(v) if v is not None else 0


async def emit_avtonet_ad_update(
    emit: EmitFn,
    row: AvtonetAd,
    *,
    source: str,
    scrape_entry: dict[str, Any],
) -> None:
    if emit is None:
        return
    await emit(
        make_event(
            "avtonet_ad_update",
            source=source,
            message=f"avtonet ad {row.ad_id} updated",
            data={
                "ad_id": int(row.ad_id),
                "status": row.status,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                "scrape": scrape_entry,
            },
        )
    )


async def record_avtonet_ad_scrape(
    db: AsyncSession,
    ad_id: int,
    *,
    source: str,
    result: str,
    fetched_at: datetime,
    http_status: int | None = None,
    detail: str | None = None,
    emit: EmitFn = None,
) -> None:
    entry: dict[str, Any] = {
        "at": fetched_at.isoformat(),
        "source": source,
        "result": result,
    }
    if http_status is not None:
        entry["http_status"] = http_status
    if detail:
        entry["detail"] = detail[:500]

    new_status = ad_status_from_scrape_result(result)
    row = await db.get(AvtonetAd, ad_id)
    if row is None:
        row = AvtonetAd(ad_id=ad_id, status=new_status, scrape_log=[entry])
        db.add(row)
    else:
        log_entries = list(row.scrape_log or [])
        log_entries.append(entry)
        row.scrape_log = log_entries
        row.status = merge_ad_status(row.status, new_status)
    await db.flush()
    if emit is not None:
        await db.refresh(row)
        await emit_avtonet_ad_update(emit, row, source=source, scrape_entry=entry)


async def record_avtonet_ad_scrape_from_outcome(
    db: AsyncSession,
    ad_id: int,
    *,
    source: str,
    outcome: str,
    fetched_at: datetime,
    http_status: int | None = None,
    detail: str | None = None,
    emit: EmitFn = None,
) -> None:
    result = scrape_result_from_outcome(outcome)
    await record_avtonet_ad_scrape(
        db,
        ad_id,
        source=source,
        result=result,
        fetched_at=fetched_at,
        http_status=http_status,
        detail=detail,
        emit=emit,
    )


async def upsert_probe(
    db: AsyncSession,
    ad_id: int,
    *,
    fetched_at: datetime,
    http_status: int,
    outcome: str,
    detail: str | None = None,
) -> None:
    stmt = (
        insert(AvtonetAdProbe)
        .values(
            ad_id=ad_id,
            fetched_at=fetched_at,
            http_status=http_status,
            gtm_ad_status=None,
            outcome=outcome,
            detail=detail,
        )
        .on_conflict_do_update(
            index_elements=[AvtonetAdProbe.ad_id],
            set_={
                "fetched_at": fetched_at,
                "http_status": http_status,
                "gtm_ad_status": None,
                "outcome": outcome,
                "detail": detail,
            },
        )
    )
    await db.execute(stmt)
    await db.flush()


async def upsert_lookahead_state(
    db: AsyncSession,
    ad_id: int,
    *,
    now: datetime,
    last_outcome: str,
    detail: str | None = None,
) -> None:
    stmt = (
        insert(AvtonetAdState)
        .values(
            ad_id=ad_id,
            status=STATUS_LOOKAHEAD,
            last_lookahead_at=now,
            last_outcome=last_outcome,
            last_detail=detail,
        )
        .on_conflict_do_update(
            index_elements=[AvtonetAdState.ad_id],
            set_={
                "status": STATUS_LOOKAHEAD,
                "last_lookahead_at": now,
                "last_outcome": last_outcome,
                "last_detail": detail,
            },
        )
    )
    await db.execute(stmt)
    await db.flush()


async def delete_lookahead_below_ad(db: AsyncSession, before_ad_id: int) -> None:
    await db.execute(
        delete(AvtonetAdState).where(
            AvtonetAdState.ad_id < before_ad_id,
            AvtonetAdState.status == STATUS_LOOKAHEAD,
        )
    )
    await db.flush()


async def upsert_expired_state(
    db: AsyncSession,
    ad_id: int,
    *,
    now: datetime,
    last_outcome: str,
    detail: str | None = None,
) -> None:
    stmt = (
        insert(AvtonetAdState)
        .values(
            ad_id=ad_id,
            status=STATUS_EXPIRED,
            last_lookahead_at=now,
            first_fallback_scrape_at=None,
            last_fallback_scrape_at=None,
            last_outcome=last_outcome,
            last_detail=detail,
        )
        .on_conflict_do_update(
            index_elements=[AvtonetAdState.ad_id],
            set_={
                "status": STATUS_EXPIRED,
                "last_lookahead_at": now,
                "first_fallback_scrape_at": None,
                "last_fallback_scrape_at": None,
                "last_outcome": last_outcome,
                "last_detail": detail,
            },
        )
    )
    await db.execute(stmt)
    await db.flush()


async def promote_lookahead_below_to_pending_fallback(
    db: AsyncSession,
    found_ad_id: int,
    *,
    now: datetime,
) -> None:
    await db.execute(
        update(AvtonetAdState)
        .where(
            AvtonetAdState.ad_id < found_ad_id,
            AvtonetAdState.status == STATUS_LOOKAHEAD,
        )
        .values(
            status=STATUS_PENDING_FALLBACK,
            first_fallback_scrape_at=now,
            last_lookahead_at=None,
            last_outcome=None,
            last_detail=None,
        )
    )
    await db.flush()


async def delete_ad_state(db: AsyncSession, ad_id: int) -> None:
    await db.execute(delete(AvtonetAdState).where(AvtonetAdState.ad_id == ad_id))
    await db.flush()


async def emit_progress_tick(
    emit: EmitFn,
    *,
    scraper_name: str,
    ad_id: int,
    last_working_ad_id: int,
    high_water: int,
    outcome: str,
    http_status: int,
) -> None:
    if emit is None:
        return
    await emit(
        make_event(
            "avtonet_progress_tick",
            source=scraper_name,
            message=f"probe {ad_id} → {outcome}",
            data={
                "ad_id": ad_id,
                "last_working_ad_id": last_working_ad_id,
                "high_water": high_water,
                "outcome": outcome,
                "http_status": http_status,
                "gtm_ad_status": None,
            },
        )
    )


async def probe_ad_id(
    client: httpx.AsyncClient,
    db: AsyncSession,
    ad_id: int,
    *,
    source_name: str,
    emit: EmitFn = None,
    last_working_ad_id: int = 0,
    high_water: int = 0,
    settings: Settings | None = None,
) -> PipelineKind | None:
    """Probe one ad ID; persist probe/scrape rows. Returns None after hard HTTP failure."""
    settings = settings or get_settings()
    now = datetime.now(timezone.utc)

    for attempt in range(SCOUT_HTTP_RETRIES):
        result = await fetch_probe(
            client,
            ad_id,
            settings=settings,
            emit=emit,
            source=source_name,
        )
        kind = pipeline_kind_from_probe(result)
        oc = outcome_from_class(kind)
        http_st = result.http_status

        await upsert_probe(
            db,
            ad_id,
            fetched_at=now,
            http_status=http_st,
            outcome=oc,
            detail=result.detail,
        )
        await record_avtonet_ad_scrape_from_outcome(
            db,
            ad_id,
            source=source_name,
            outcome=oc,
            fetched_at=now,
            http_status=http_st,
            detail=result.detail,
            emit=emit,
        )
        await emit_progress_tick(
            emit,
            scraper_name=source_name,
            ad_id=ad_id,
            last_working_ad_id=last_working_ad_id,
            high_water=high_water,
            outcome=oc,
            http_status=http_st,
        )

        if result.http_status < 0:
            if attempt + 1 < SCOUT_HTTP_RETRIES:
                continue
            return None

        if kind in ("not_found", "bad_status") and attempt + 1 < SCOUT_HTTP_RETRIES:
            if result.kind in ("cloudflare", "blocked"):
                continue
        return kind

    return "bad_status"
