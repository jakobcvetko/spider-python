"""avto.net backfill for IDs skipped during lookahead (mirrors bolha.backfill)."""

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
from app.models import AvtonetAdState
from scraper.base import ScrapedItem, get_listing_id, upsert_items
from scraper.sources.avto_net_common import LISTING_SOURCE
from scraper.sources.avto_net_probe import probe_ad_id as fetch_probe
from scraper.sources.avtonet_pipeline import (
    EmitFn,
    FALLBACK_CYCLE_PAUSE_SECONDS,
    FALLBACK_TIMEOUT_SECONDS,
    MAX_FALLBACK_IDS_PER_FETCH,
    STATUS_FALLBACK_WARMING,
    STATUS_PENDING_FALLBACK,
    STATUS_TIMED_OUT,
    delete_ad_state,
    emit_progress_tick,
    get_meta,
    outcome_from_class,
    pipeline_kind_from_probe,
    record_avtonet_ad_scrape_from_outcome,
    upsert_probe,
)

log = logging.getLogger(__name__)


def _fallback_age_seconds(st: AvtonetAdState, now: datetime) -> float | None:
    if st.first_fallback_scrape_at is None:
        return None
    return (now - st.first_fallback_scrape_at).total_seconds()


async def _mark_timed_out(
    db: AsyncSession,
    ad_id: int,
    *,
    now: datetime,
) -> None:
    await db.execute(
        update(AvtonetAdState)
        .where(AvtonetAdState.ad_id == ad_id)
        .values(
            status=STATUS_TIMED_OUT,
            last_fallback_scrape_at=now,
            last_outcome="timed_out",
            last_detail=None,
        )
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
                await asyncio.sleep(FALLBACK_CYCLE_PAUSE_SECONDS)
                return []

            stmt = (
                select(AvtonetAdState)
                .where(
                    AvtonetAdState.ad_id < lw,
                    AvtonetAdState.status.in_(
                        [STATUS_PENDING_FALLBACK, STATUS_FALLBACK_WARMING]
                    ),
                )
                .order_by(AvtonetAdState.ad_id.desc())
                .limit(MAX_FALLBACK_IDS_PER_FETCH)
            )
            rows = (await db.execute(stmt)).scalars().all()
            collected: list[ScrapedItem] = []
            now = datetime.now(timezone.utc)

            for st in rows:
                ad_id = st.ad_id
                age_s = _fallback_age_seconds(st, now)
                if age_s is not None and age_s >= FALLBACK_TIMEOUT_SECONDS:
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
                    age_s = _fallback_age_seconds(st, now)
                    if age_s is not None and age_s >= FALLBACK_TIMEOUT_SECONDS:
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
                    listing_id = await get_listing_id(db, LISTING_SOURCE, str(ad_id))
                    if listing_id is None:
                        try:
                            await upsert_items(db, LISTING_SOURCE, [result.item])
                            listing_id = await get_listing_id(
                                db, LISTING_SOURCE, str(ad_id)
                            )
                        except Exception:
                            log.exception(
                                "avto.net backfill: upsert failed ad_id=%s", ad_id
                            )
                    if listing_id is not None:
                        try:
                            await enqueue_matcher_job(db, listing_id)
                        except Exception:
                            log.exception(
                                "avto.net backfill: matcher enqueue failed ad_id=%s",
                                ad_id,
                            )
                    continue

                if kind == "expired":
                    await delete_ad_state(db, ad_id)
                    continue

                age_s = _fallback_age_seconds(st, now)
                if age_s is not None and age_s >= FALLBACK_TIMEOUT_SECONDS:
                    await _mark_timed_out(db, ad_id, now=now)
                    continue

                if st.status == STATUS_PENDING_FALLBACK:
                    values: dict[str, object] = {
                        "status": STATUS_FALLBACK_WARMING,
                        "last_fallback_scrape_at": now,
                        "last_outcome": oc,
                        "last_detail": result.detail,
                    }
                    if st.first_fallback_scrape_at is None:
                        values["first_fallback_scrape_at"] = now
                    await db.execute(
                        update(AvtonetAdState)
                        .where(AvtonetAdState.ad_id == ad_id)
                        .values(**values)
                    )
                else:
                    await db.execute(
                        update(AvtonetAdState)
                        .where(AvtonetAdState.ad_id == ad_id)
                        .values(
                            last_fallback_scrape_at=now,
                            last_outcome=oc,
                            last_detail=result.detail,
                        )
                    )

            await db.commit()
            log.info(
                "avto.net backfill: processed up to %s ids, collected %s active",
                len(rows),
                len(collected),
            )

        await asyncio.sleep(FALLBACK_CYCLE_PAUSE_SECONDS)
        return collected
