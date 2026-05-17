from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal
from app.matcher_jobs import enqueue_matcher_job
from app.models import BolhaAd
from app.models.bolha_ad import (
    AD_STATUS_BACKFILL,
    AD_STATUS_SUCCESS,
    AD_STATUS_TIMEDOUT,
)
from scraper.base import ScrapedItem, get_listing_id, upsert_items
from scraper.http_retries import httpx_get_with_retries
from scraper.sources.bolha_common import (
    AD_PROBE_URL_TEMPLATE,
    BACKFILL_BATCH_SIZE,
    BACKFILL_CYCLE_PAUSE_SECONDS,
    BACKFILL_TIMEOUT_SECONDS,
    EmitFn,
    LISTING_SOURCE,
    SCOUT_HTTP_RETRIES,
    classify_probe_response,
    emit_progress_tick,
    get_meta,
    outcome_from_class,
    parse_active_detail,
    record_bolha_ad_scrape,
    record_bolha_ad_scrape_from_outcome,
)

log = logging.getLogger(__name__)


def _backfill_age_seconds(row: BolhaAd, now: datetime) -> float | None:
    if row.backfill_started_at is None:
        return None
    return (now - row.backfill_started_at).total_seconds()


async def _mark_timed_out(db: AsyncSession, ad_id: int, *, now: datetime) -> None:
    await db.execute(
        update(BolhaAd)
        .where(BolhaAd.ad_id == ad_id)
        .values(status=AD_STATUS_TIMEDOUT, backfill_started_at=None)
    )


class BolhaBackfillSource:
    name = "bolha.backfill"
    listing_source = LISTING_SOURCE

    async def fetch(
        self,
        client: httpx.AsyncClient,
        emit: EmitFn = None,
    ) -> list[ScrapedItem]:
        async with SessionLocal() as db:
            meta = await get_meta(db)
            lw = int(meta.last_working_ad_id or 0)
            if lw <= 0:
                await asyncio.sleep(BACKFILL_CYCLE_PAUSE_SECONDS)
                return []

            stmt = (
                select(BolhaAd)
                .where(
                    BolhaAd.ad_id < lw,
                    BolhaAd.status == AD_STATUS_BACKFILL,
                )
                .order_by(BolhaAd.ad_id.desc())
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

                url = AD_PROBE_URL_TEMPLATE.format(ad_id=ad_id)
                try:
                    resp = await httpx_get_with_retries(
                        client,
                        url,
                        timeout=25.0,
                        max_attempts=SCOUT_HTTP_RETRIES,
                    )
                except httpx.HTTPError as e:
                    log.warning("bolha backfill: probe %s failed: %s", ad_id, e)
                    await record_bolha_ad_scrape(
                        db,
                        ad_id,
                        source=self.name,
                        result="error",
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
                        gtm_ad_status=None,
                    )
                    age_s = _backfill_age_seconds(row, now)
                    if age_s is not None and age_s >= BACKFILL_TIMEOUT_SECONDS:
                        await _mark_timed_out(db, ad_id, now=now)
                    continue

                html = resp.text
                kind, gtm, _d, http_st = classify_probe_response(
                    resp, html, ad_id=ad_id
                )
                oc = outcome_from_class(kind)

                await record_bolha_ad_scrape_from_outcome(
                    db,
                    ad_id,
                    source=self.name,
                    outcome=oc,
                    fetched_at=now,
                    http_status=http_st,
                    emit=emit,
                )
                await emit_progress_tick(
                    emit,
                    scraper_name=self.name,
                    ad_id=ad_id,
                    last_working_ad_id=lw,
                    high_water=int(meta.last_fetch_high_water or 0),
                    outcome=oc,
                    http_status=http_st,
                    gtm_ad_status=gtm,
                )

                if kind == "active":
                    item = parse_active_detail(html, ad_id)
                    collected.append(item)
                    try:
                        await upsert_items(db, LISTING_SOURCE, [item])
                    except Exception:
                        log.exception("bolha backfill: upsert failed ad_id=%s", ad_id)
                    listing_id = await get_listing_id(db, LISTING_SOURCE, str(ad_id))
                    if listing_id is not None:
                        try:
                            await enqueue_matcher_job(db, listing_id)
                        except Exception:
                            log.exception(
                                "bolha backfill: matcher enqueue failed ad_id=%s", ad_id
                            )
                    await db.execute(
                        update(BolhaAd)
                        .where(BolhaAd.ad_id == ad_id)
                        .values(status=AD_STATUS_SUCCESS, backfill_started_at=None)
                    )
                    continue

                if kind == "expired":
                    await db.execute(
                        update(BolhaAd)
                        .where(BolhaAd.ad_id == ad_id)
                        .values(backfill_started_at=None)
                    )
                    continue

                age_s = _backfill_age_seconds(row, now)
                if age_s is not None and age_s >= BACKFILL_TIMEOUT_SECONDS:
                    await _mark_timed_out(db, ad_id, now=now)

            await db.commit()
            log.info(
                "bolha backfill: processed up to %s ids, collected %s active",
                len(rows),
                len(collected),
            )

        await asyncio.sleep(BACKFILL_CYCLE_PAUSE_SECONDS)
        return collected
