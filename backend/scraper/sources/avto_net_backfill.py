"""avto.net backfill for gap IDs below last_working (mirrors bolha.backfill)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import SessionLocal
from app.matcher_jobs import enqueue_matcher_job
from app.models import AvtonetAd
from app.models.avtonet_ad import (
    AD_STATUS_BACKFILL,
    AD_STATUS_SUCCESS,
    AD_STATUS_TIMEDOUT,
)
from scraper.base import ScrapedItem, get_listing_id, upsert_items
from scraper.sources.avto_net_common import LISTING_SOURCE
from scraper.sources.avto_net_probe import probe_ad_id as fetch_probe
from scraper.sources.avtonet_pipeline import (
    BACKFILL_BATCH_SIZE,
    BACKFILL_CYCLE_PAUSE_SECONDS,
    BACKFILL_TIMEOUT_SECONDS,
    EmitFn,
    delete_ad_state,
    emit_progress_tick,
    get_meta,
    outcome_from_class,
    pipeline_kind_from_probe,
    record_avtonet_ad_scrape_from_outcome,
    upsert_probe,
)

log = logging.getLogger(__name__)


def _backfill_age_seconds(row: AvtonetAd, now: datetime) -> float | None:
    if row.backfill_started_at is None:
        return None
    return (now - row.backfill_started_at).total_seconds()


async def _mark_timed_out(db: AsyncSession, ad_id: int, *, now: datetime) -> None:
    await db.execute(
        update(AvtonetAd)
        .where(AvtonetAd.ad_id == ad_id)
        .values(status=AD_STATUS_TIMEDOUT, backfill_started_at=None)
    )


class AvtoNetBackfillSource:
    name = "avto.net.backfill"
    listing_source = LISTING_SOURCE

    async def fetch(
        self,
        client: httpx.AsyncClient,
        emit: EmitFn = None,
    ) -> list[ScrapedItem]:
        settings = get_settings()
        async with SessionLocal() as db:
            meta = await get_meta(db)
            lw = int(meta.last_working_ad_id or 0)
            if lw <= 0:
                await asyncio.sleep(BACKFILL_CYCLE_PAUSE_SECONDS)
                return []

            stmt = (
                select(AvtonetAd)
                .where(
                    AvtonetAd.ad_id < lw,
                    AvtonetAd.status == AD_STATUS_BACKFILL,
                )
                .order_by(AvtonetAd.ad_id.desc())
                .limit(BACKFILL_BATCH_SIZE)
            )
            rows = (await db.execute(stmt)).scalars().all()
            collected: list[ScrapedItem] = []
            now = datetime.now(timezone.utc)

            for row in rows:
                ad_id = row.ad_id
                age_s = _backfill_age_seconds(row, now)
                if age_s is not None and age_s >= BACKFILL_TIMEOUT_SECONDS:
                    await _mark_timed_out(db, ad_id, now=now)
                    continue

                try:
                    result = await fetch_probe(
                        client,
                        ad_id,
                        settings=settings,
                        emit=emit,
                        source=self.name,
                    )
                except httpx.HTTPError as e:
                    log.warning("avto.net backfill: probe %s failed: %s", ad_id, e)
                    await upsert_probe(
                        db,
                        ad_id,
                        fetched_at=now,
                        http_status=-1,
                        outcome="http_error",
                        detail=str(e)[:500],
                    )
                    await record_avtonet_ad_scrape_from_outcome(
                        db,
                        ad_id,
                        source=self.name,
                        outcome="http_error",
                        fetched_at=now,
                        http_status=-1,
                        detail=str(e),
                        emit=emit,
                    )
                    await emit_progress_tick(
                        emit,
                        scraper_name=self.name,
                        ad_id=ad_id,
                        last_working_ad_id=lw,
                        high_water=int(meta.last_fetch_high_water or 0),
                        outcome="http_error",
                        http_status=-1,
                    )
                    age_s = _backfill_age_seconds(row, now)
                    if age_s is not None and age_s >= BACKFILL_TIMEOUT_SECONDS:
                        await _mark_timed_out(db, ad_id, now=now)
                    continue

                kind = pipeline_kind_from_probe(result)
                oc = outcome_from_class(kind)

                await upsert_probe(
                    db,
                    ad_id,
                    fetched_at=now,
                    http_status=result.http_status,
                    outcome=oc,
                    detail=result.detail,
                )
                await record_avtonet_ad_scrape_from_outcome(
                    db,
                    ad_id,
                    source=self.name,
                    outcome=oc,
                    fetched_at=now,
                    http_status=result.http_status,
                    detail=result.detail,
                    emit=emit,
                )
                await emit_progress_tick(
                    emit,
                    scraper_name=self.name,
                    ad_id=ad_id,
                    last_working_ad_id=lw,
                    high_water=int(meta.last_fetch_high_water or 0),
                    outcome=oc,
                    http_status=result.http_status,
                )

                if kind == "active" and result.item is not None:
                    collected.append(result.item)
                    await delete_ad_state(db, ad_id)
                    try:
                        await upsert_items(db, LISTING_SOURCE, [result.item])
                    except Exception:
                        log.exception("avto.net backfill: upsert failed ad_id=%s", ad_id)
                    listing_id = await get_listing_id(db, LISTING_SOURCE, str(ad_id))
                    if listing_id is not None:
                        try:
                            await enqueue_matcher_job(db, listing_id)
                        except Exception:
                            log.exception(
                                "avto.net backfill: matcher enqueue failed ad_id=%s",
                                ad_id,
                            )
                    await db.execute(
                        update(AvtonetAd)
                        .where(AvtonetAd.ad_id == ad_id)
                        .values(status=AD_STATUS_SUCCESS, backfill_started_at=None)
                    )
                    continue

                if kind == "expired":
                    await delete_ad_state(db, ad_id)
                    await db.execute(
                        update(AvtonetAd)
                        .where(AvtonetAd.ad_id == ad_id)
                        .values(backfill_started_at=None)
                    )
                    continue

                age_s = _backfill_age_seconds(row, now)
                if age_s is not None and age_s >= BACKFILL_TIMEOUT_SECONDS:
                    await _mark_timed_out(db, ad_id, now=now)

            await db.commit()
            log.info(
                "avto.net backfill: processed up to %s ids, collected %s active",
                len(rows),
                len(collected),
            )

        await asyncio.sleep(BACKFILL_CYCLE_PAUSE_SECONDS)
        return collected
