"""avto.net ad registry + admin WebSocket events (mirrors bolha registry pattern)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models.avtonet_ad import (
    AD_STATUS_PENDING,
    AD_STATUS_REMOVED,
    AD_STATUS_SUCCESS,
    AvtonetAd,
    SCRAPE_RESULT_ERROR,
    SCRAPE_RESULT_REMOVED,
    SCRAPE_RESULT_SUCCESS,
)
from app.models.avtonet_scrape_meta import AvtonetScrapeMeta
from app.scraper_events import make_event
from scraper.sources.avto_net_common import (
    LISTING_SOURCE,
    SCOUT_HTTP_RETRIES,
    ProbeKind,
)

log = logging.getLogger(__name__)

EmitFn = Any


def scrape_result_from_kind(kind: ProbeKind) -> str:
    if kind == "active":
        return SCRAPE_RESULT_SUCCESS
    if kind == "not_found":
        return SCRAPE_RESULT_REMOVED
    return SCRAPE_RESULT_ERROR


def ad_status_from_scrape_result(result: str) -> str:
    if result == SCRAPE_RESULT_SUCCESS:
        return AD_STATUS_SUCCESS
    if result == SCRAPE_RESULT_REMOVED:
        return AD_STATUS_REMOVED
    return AD_STATUS_PENDING


def merge_ad_status(current: str, new: str) -> str:
    # Success is sticky except when the ad is confirmed gone.
    if new == AD_STATUS_REMOVED:
        return AD_STATUS_REMOVED
    if new == AD_STATUS_SUCCESS:
        return AD_STATUS_SUCCESS
    if current == AD_STATUS_SUCCESS:
        return AD_STATUS_SUCCESS
    return new


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


async def record_avtonet_probe(
    db: AsyncSession,
    ad_id: int,
    *,
    source: str,
    kind: ProbeKind,
    fetched_at: datetime,
    http_status: int | None = None,
    detail: str | None = None,
    emit: EmitFn = None,
) -> None:
    result = scrape_result_from_kind(kind)
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


def is_known_probe_kind(kind: ProbeKind) -> bool:
    """IDs that exist as real detail pages (scout frontier is last known)."""
    return kind == "active"


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


async def probe_ad_id(
    client,
    db: AsyncSession,
    ad_id: int,
    *,
    source_name: str,
    emit: EmitFn = None,
    last_working_ad_id: int = 0,
    settings: Settings | None = None,
) -> ProbeKind | None:
    """Probe one ad ID for scout; persist scrape row. Returns None on hard HTTP failure."""
    from scraper.sources.avto_net_lookahead import probe_ad_id as fetch_probe

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
        await record_avtonet_probe(
            db,
            ad_id,
            source=source_name,
            kind=result.kind,
            fetched_at=now,
            http_status=result.http_status,
            detail=result.detail,
            emit=emit,
        )
        await emit_avtonet_progress_tick(
            emit,
            scraper_name=source_name,
            ad_id=ad_id,
            last_working_ad_id=last_working_ad_id,
            outcome=result.kind,
            http_status=result.http_status,
        )
        if result.http_status < 0:
            if attempt + 1 < SCOUT_HTTP_RETRIES:
                continue
            return None
        if result.kind in ("not_found", "unknown", "redirect") and attempt + 1 < SCOUT_HTTP_RETRIES:
            continue
        if result.kind in ("cloudflare", "blocked") and attempt + 1 < SCOUT_HTTP_RETRIES:
            continue
        return result.kind

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
