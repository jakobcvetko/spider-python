from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select, update

from app.database import SessionLocal
from app.models import BolhaAdState
from scraper.base import ScrapedItem
from scraper.sources.bolha_common import (
    AD_PROBE_URL_TEMPLATE,
    EmitFn,
    FALLBACK_CYCLE_PAUSE_SECONDS,
    FALLBACK_TIMEOUT_SECONDS,
    LISTING_SOURCE,
    MAX_FALLBACK_IDS_PER_FETCH,
    STATUS_FALLBACK_WARMING,
    STATUS_PENDING_FALLBACK,
    STATUS_TIMED_OUT,
    classify_probe_response,
    delete_ad_state,
    emit_progress_tick,
    get_meta,
    outcome_from_class,
    parse_active_detail,
    record_bolha_ad_scrape,
    record_bolha_ad_scrape_from_outcome,
    upsert_probe,
)

log = logging.getLogger(__name__)


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
                await asyncio.sleep(FALLBACK_CYCLE_PAUSE_SECONDS)
                return []

            stmt = (
                select(BolhaAdState)
                .where(
                    BolhaAdState.ad_id < lw,
                    BolhaAdState.status.in_(
                        [STATUS_PENDING_FALLBACK, STATUS_FALLBACK_WARMING]
                    ),
                )
                .order_by(BolhaAdState.ad_id.desc())
                .limit(MAX_FALLBACK_IDS_PER_FETCH)
            )
            rows = (await db.execute(stmt)).scalars().all()
            collected: list[ScrapedItem] = []
            now = datetime.now(timezone.utc)

            for st in rows:
                ad_id = st.ad_id
                url = AD_PROBE_URL_TEMPLATE.format(ad_id=ad_id)
                try:
                    resp = await client.get(url, timeout=25.0)
                except httpx.HTTPError as e:
                    log.warning("bolha backfill: probe %s failed: %s", ad_id, e)
                    await upsert_probe(
                        db,
                        ad_id,
                        fetched_at=now,
                        http_status=-1,
                        gtm_ad_status=None,
                        outcome="http_error",
                        detail=str(e)[:500],
                    )
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
                    continue

                html = resp.text
                kind, gtm, _d, http_st = classify_probe_response(
                    resp, html, ad_id=ad_id
                )
                oc = outcome_from_class(kind)

                await upsert_probe(
                    db,
                    ad_id,
                    fetched_at=now,
                    http_status=http_st,
                    gtm_ad_status=gtm,
                    outcome=oc,
                    detail=None,
                )
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
                    collected.append(parse_active_detail(html, ad_id))
                    await delete_ad_state(db, ad_id)
                    continue

                if kind == "expired":
                    await delete_ad_state(db, ad_id)
                    continue

                if st.status == STATUS_PENDING_FALLBACK:
                    await db.execute(
                        update(BolhaAdState)
                        .where(BolhaAdState.ad_id == ad_id)
                        .values(
                            status=STATUS_FALLBACK_WARMING,
                            first_fallback_scrape_at=now,
                            last_fallback_scrape_at=now,
                            last_outcome=oc,
                            last_detail=None,
                        )
                    )
                else:
                    first_at = st.first_fallback_scrape_at or now
                    age_s = (now - first_at).total_seconds()
                    if age_s >= FALLBACK_TIMEOUT_SECONDS:
                        await db.execute(
                            update(BolhaAdState)
                            .where(BolhaAdState.ad_id == ad_id)
                            .values(
                                status=STATUS_TIMED_OUT,
                                last_fallback_scrape_at=now,
                                last_outcome="timed_out",
                                last_detail=None,
                            )
                        )
                    else:
                        await db.execute(
                            update(BolhaAdState)
                            .where(BolhaAdState.ad_id == ad_id)
                            .values(
                                last_fallback_scrape_at=now,
                                last_outcome=oc,
                                last_detail=None,
                            )
                        )

            await db.commit()
            log.info(
                "bolha backfill: processed up to %s ids, collected %s active",
                len(rows),
                len(collected),
            )

        await asyncio.sleep(FALLBACK_CYCLE_PAUSE_SECONDS)
        return collected
