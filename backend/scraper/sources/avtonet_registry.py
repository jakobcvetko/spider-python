"""avto.net ad registry + admin WebSocket events (mirrors bolha registry pattern)."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.matcher_jobs import enqueue_matcher_job
from app.models.avtonet_ad import (
    AD_STATUS_PENDING,
    AD_STATUS_SUCCESS,
    AvtonetAd,
    SCRAPE_RESULT_EMPTY,
    SCRAPE_RESULT_ERROR,
    SCRAPE_RESULT_SUCCESS,
)
from app.models.avtonet_scrape_meta import AvtonetScrapeMeta
from app.scraper_events import make_event
from scraper.base import get_listing_id, upsert_items
from scraper.sources.avto_net_common import LISTING_SOURCE, ProbeKind
from scraper.sources.avto_net_probe import ProbeResult, probe_ad_id as fetch_probe

log = logging.getLogger(__name__)

EmitFn = Any


@dataclass(frozen=True)
class AvtonetProbeOutcome:
    """Result after persisting a probe. Only pending and success row statuses."""

    confirmed: bool
    status: str
    scrape_result: str
    kind: ProbeKind


def ad_status_from_scrape_result(result: str) -> str:
    if result == SCRAPE_RESULT_SUCCESS:
        return AD_STATUS_SUCCESS
    return AD_STATUS_PENDING


def merge_ad_status(current: str, new: str) -> str:
    if new == AD_STATUS_SUCCESS:
        return AD_STATUS_SUCCESS
    return AD_STATUS_PENDING


async def get_meta(db: AsyncSession) -> AvtonetScrapeMeta:
    row = await db.get(AvtonetScrapeMeta, 1)
    if row is None:
        row = AvtonetScrapeMeta(id=1)
        db.add(row)
        await db.flush()
    return row


async def meta_set_last_working(db: AsyncSession, ad_id: int) -> None:
    meta = await get_meta(db)
    meta.last_working_ad_id = ad_id
    meta.last_working_at = datetime.now(timezone.utc)


async def meta_begin_batch(db: AsyncSession) -> None:
    meta = await get_meta(db)
    meta.last_batch_started_at = datetime.now(timezone.utc)


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


async def apply_avtonet_probe(
    db: AsyncSession,
    result: ProbeResult,
    *,
    source: str,
    fetched_at: datetime,
    emit: EmitFn = None,
    enqueue_matcher: bool = True,
) -> AvtonetProbeOutcome:
    """Persist probe outcome: pending = empty/transient, success = listing stored."""
    if result.kind == "not_found":
        scrape_result = SCRAPE_RESULT_EMPTY
        confirmed = False
    elif result.kind == "active" and result.item is not None:
        listing_id: uuid.UUID | None = None
        try:
            await upsert_items(
                db, LISTING_SOURCE, [result.item], commit=False
            )
            listing_id = await get_listing_id(db, LISTING_SOURCE, str(result.ad_id))
            if listing_id is not None and enqueue_matcher:
                await enqueue_matcher_job(db, listing_id)
        except Exception:
            log.exception(
                "avto.net: listing upsert failed ad_id=%s source=%s",
                result.ad_id,
                source,
            )
            listing_id = await get_listing_id(db, LISTING_SOURCE, str(result.ad_id))

        if listing_id is not None:
            scrape_result = SCRAPE_RESULT_SUCCESS
            confirmed = True
        else:
            scrape_result = SCRAPE_RESULT_ERROR
            confirmed = False
    else:
        scrape_result = SCRAPE_RESULT_ERROR
        confirmed = False

    status = ad_status_from_scrape_result(scrape_result)
    await record_avtonet_ad_scrape(
        db,
        result.ad_id,
        source=source,
        result=scrape_result,
        fetched_at=fetched_at,
        http_status=result.http_status,
        detail=result.detail,
        emit=emit,
    )
    return AvtonetProbeOutcome(
        confirmed=confirmed,
        status=status,
        scrape_result=scrape_result,
        kind=result.kind,
    )


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


async def scout_probe_ad_id(
    client: httpx.AsyncClient,
    db: AsyncSession,
    ad_id: int,
    *,
    source_name: str,
    emit: EmitFn = None,
    last_working_ad_id: int = 0,
    settings: Settings | None = None,
) -> AvtonetProbeOutcome | None:
    """Probe one ad ID for scout; persist row + listing. None on hard HTTP failure."""
    from scraper.sources.avto_net_common import SCOUT_HTTP_RETRIES

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
        outcome = await apply_avtonet_probe(
            db,
            result,
            source=source_name,
            fetched_at=now,
            emit=emit,
        )
        tick_lw = last_working_ad_id
        if outcome.confirmed:
            tick_lw = ad_id
        await emit_avtonet_progress_tick(
            emit,
            scraper_name=source_name,
            ad_id=ad_id,
            last_working_ad_id=tick_lw,
            outcome=outcome.scrape_result,
            http_status=result.http_status,
        )
        if result.http_status < 0:
            return None
        if result.kind in ("not_found", "unknown", "redirect"):
            return outcome
        if result.kind in ("cloudflare", "blocked") and attempt + 1 < SCOUT_HTTP_RETRIES:
            continue
        return outcome

    return None


async def emit_avtonet_progress_tick(
    emit: EmitFn,
    *,
    scraper_name: str,
    ad_id: int,
    last_working_ad_id: int,
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
                "outcome": outcome,
                "http_status": http_status,
            },
        )
    )
