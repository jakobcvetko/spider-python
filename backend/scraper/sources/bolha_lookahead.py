from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import NoReturn

import httpx

from app.database import SessionLocal
from scraper.base import upsert_items
from scraper.sources.bolha_common import (
    AD_PROBE_URL_TEMPLATE,
    EmitFn,
    IAPI_HOME_URL,
    LISTING_SOURCE,
    LOOKAHEAD_ADS,
    LOOKAHEAD_TIMEOUT_SECONDS,
    classify_probe_response,
    delete_ad_state,
    delete_lookahead_below_ad,
    emit_progress_tick,
    get_meta,
    max_ad_id_from_homepage_html,
    max_numeric_listing_id,
    meta_begin_fetch,
    meta_set_last_working,
    outcome_from_class,
    parse_active_detail,
    promote_lookahead_below_to_pending_fallback,
    upsert_expired_state,
    upsert_lookahead_state,
    upsert_probe,
)

log = logging.getLogger(__name__)


class BolhaLookaheadSource:
    name = "bolha.lookahead"
    listing_source = LISTING_SOURCE

    async def fetch(
        self,
        client: httpx.AsyncClient,
        emit: EmitFn = None,
    ) -> NoReturn:
        """Runs until process exit (worker uses no interval job for this source)."""
        while True:
            async with SessionLocal() as db:
                try:
                    home = await client.get(IAPI_HOME_URL, timeout=25.0)
                except httpx.HTTPError as e:
                    log.warning("bolha lookahead: homepage request failed: %s", e)
                    await asyncio.sleep(LOOKAHEAD_TIMEOUT_SECONDS)
                    continue

                if home.status_code != 200:
                    log.warning(
                        "bolha lookahead: homepage returned status %s",
                        home.status_code,
                    )
                    await asyncio.sleep(LOOKAHEAD_TIMEOUT_SECONDS)
                    continue

                # hp_max = max_ad_id_from_homepage_html(home.text)
                db_max = await max_numeric_listing_id(db)
                # high = max(hp_max, db_max)
                high = db_max

                await meta_begin_fetch(db, high=high)
                meta = await get_meta(db)
                anchor = max(high, int(meta.last_working_ad_id or 0))
                log.info(
                    "bolha lookahead: batch db_max=%s high_water=%s anchor=%s",
                    db_max,
                    high,
                    anchor,
                )

                batch_resolved = False
                for k in range(1, LOOKAHEAD_ADS + 1):
                    ad_id = anchor + k
                    url = AD_PROBE_URL_TEMPLATE.format(ad_id=ad_id)
                    now = datetime.now(timezone.utc)
                    try:
                        resp = await client.get(url, timeout=25.0)
                    except httpx.HTTPError as e:
                        log.warning("bolha lookahead: probe %s failed: %s", ad_id, e)
                        await upsert_probe(
                            db,
                            ad_id,
                            fetched_at=now,
                            http_status=-1,
                            gtm_ad_status=None,
                            outcome="http_error",
                            detail=str(e)[:500],
                        )
                        await upsert_lookahead_state(
                            db,
                            ad_id,
                            now=now,
                            last_outcome="http_error",
                            detail=str(e)[:500],
                        )
                        await emit_progress_tick(
                            emit,
                            scraper_name=self.name,
                            ad_id=ad_id,
                            last_working_ad_id=anchor,
                            high_water=high,
                            outcome="http_error",
                            http_status=-1,
                            gtm_ad_status=None,
                        )
                        continue

                    html = resp.text
                    kind, gtm, _detail, http_st = classify_probe_response(
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

                    if kind == "active":
                        await emit_progress_tick(
                            emit,
                            scraper_name=self.name,
                            ad_id=ad_id,
                            last_working_ad_id=anchor,
                            high_water=high,
                            outcome=oc,
                            http_status=http_st,
                            gtm_ad_status=gtm,
                        )
                        item = parse_active_detail(html, ad_id)
                        await promote_lookahead_below_to_pending_fallback(
                            db, ad_id, now=now
                        )
                        await delete_ad_state(db, ad_id)
                        await meta_set_last_working(db, ad_id)
                        await db.commit()

                        try:
                            async with SessionLocal() as db_ins:
                                inserted = await upsert_items(
                                    db_ins, LISTING_SOURCE, [item]
                                )
                        except Exception:
                            log.exception(
                                "bolha lookahead: upsert failed for ad_id=%s",
                                ad_id,
                            )
                            inserted = 0

                        log.info(
                            "bolha lookahead: active ad_id=%s (anchor was %s), inserted=%s",
                            ad_id,
                            anchor,
                            inserted,
                        )
                        batch_resolved = True
                        break

                    if kind == "expired":
                        await emit_progress_tick(
                            emit,
                            scraper_name=self.name,
                            ad_id=ad_id,
                            last_working_ad_id=ad_id,
                            high_water=high,
                            outcome=oc,
                            http_status=http_st,
                            gtm_ad_status=gtm,
                        )
                        await upsert_expired_state(
                            db, ad_id, now=now, last_outcome=oc, detail=None
                        )
                        await delete_lookahead_below_ad(db, ad_id)
                        await meta_set_last_working(db, ad_id)
                        await db.commit()
                        log.info(
                            "bolha lookahead: expired (redirect inactive) ad_id=%s "
                            "(anchor was %s), advanced last_working, no backfill",
                            ad_id,
                            anchor,
                        )
                        batch_resolved = True
                        break

                    await upsert_lookahead_state(
                        db,
                        ad_id,
                        now=now,
                        last_outcome=oc,
                        detail=None,
                    )
                    await emit_progress_tick(
                        emit,
                        scraper_name=self.name,
                        ad_id=ad_id,
                        last_working_ad_id=anchor,
                        high_water=high,
                        outcome=oc,
                        http_status=http_st,
                        gtm_ad_status=gtm,
                    )

                if not batch_resolved:
                    await db.commit()
                    await asyncio.sleep(LOOKAHEAD_TIMEOUT_SECONDS)
