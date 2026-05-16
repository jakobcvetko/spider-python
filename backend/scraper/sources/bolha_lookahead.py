from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import NoReturn

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal
from scraper.base import upsert_items
from scraper.sources.bolha_scout import run_bolha_scout
from scraper.sources.bolha_common import (
    AD_PROBE_URL_TEMPLATE,
    EmitFn,
    IAPI_HOME_URL,
    LISTING_SOURCE,
    LOOKAHEAD_ADS,
    LOOKAHEAD_HIGH_WATER_REFRESH_BATCHES,
    LOOKAHEAD_HOMEPAGE_REFRESH_BATCHES,
    LOOKAHEAD_PROBE_TIMEOUT_SECONDS,
    LOOKAHEAD_TIMEOUT_SECONDS,
    classify_probe_response,
    delete_ad_state,
    delete_lookahead_below_ad,
    emit_progress_tick,
    get_meta,
    max_ad_id_from_homepage_html,
    max_numeric_listing_id,
    meta_begin_fetch,
    meta_set_homepage_max,
    meta_set_last_working,
    outcome_from_class,
    parse_active_detail,
    record_bolha_ad_scrape,
    record_bolha_ad_scrape_from_outcome,
    promote_lookahead_below_to_pending_fallback,
    upsert_expired_state,
    upsert_lookahead_state,
    upsert_probe,
)

log = logging.getLogger(__name__)


def _probe_client(shared: httpx.AsyncClient) -> httpx.AsyncClient:
    """HTTP client without worker NOTIFY hooks — lookahead does many requests per second."""
    return httpx.AsyncClient(
        headers=dict(shared.headers),
        follow_redirects=True,
        timeout=httpx.Timeout(LOOKAHEAD_PROBE_TIMEOUT_SECONDS),
        limits=httpx.Limits(max_keepalive_connections=8, max_connections=16),
    )


class BolhaLookaheadSource:
    name = "bolha.lookahead"
    listing_source = LISTING_SOURCE

    def __init__(self) -> None:
        self._batch_count = 0
        self._cached_db_max: int | None = None

    async def _refresh_high_water(
        self,
        db: AsyncSession,
        probe: httpx.AsyncClient,
        *,
        meta_anchor: int,
    ) -> int:
        """Occasionally reconcile with listings MAX and homepage; otherwise trust meta."""
        self._batch_count += 1
        refresh_db = (
            self._cached_db_max is None
            or self._batch_count % LOOKAHEAD_HIGH_WATER_REFRESH_BATCHES == 0
            or meta_anchor >= (self._cached_db_max or 0)
        )
        if refresh_db:
            self._cached_db_max = await max_numeric_listing_id(db)

        high = max(meta_anchor, self._cached_db_max or 0)

        if self._batch_count % LOOKAHEAD_HOMEPAGE_REFRESH_BATCHES == 0:
            try:
                home = await probe.get(IAPI_HOME_URL, timeout=LOOKAHEAD_PROBE_TIMEOUT_SECONDS)
                if home.status_code == 200:
                    hp_max = max_ad_id_from_homepage_html(home.text)
                    await meta_set_homepage_max(db, hp_max)
                    high = max(high, hp_max)
            except httpx.HTTPError as e:
                log.warning("bolha lookahead: periodic homepage refresh failed: %s", e)

        return high

    async def fetch(
        self,
        client: httpx.AsyncClient,
        emit: EmitFn = None,
    ) -> NoReturn:
        """Runs until process exit (worker uses no interval job for this source)."""
        probe = _probe_client(client)
        try:
            async with SessionLocal() as db:
                log.info("bolha lookahead: running initial scout")
                try:
                    await run_bolha_scout(db, client, emit)
                except RuntimeError:
                    log.exception(
                        "bolha lookahead: initial scout failed; "
                        "continuing with stored anchor"
                    )

                while True:
                    meta = await get_meta(db)
                    anchor = int(meta.last_working_ad_id or 0)
                    high = await self._refresh_high_water(
                        db, probe, meta_anchor=anchor
                    )

                    await meta_begin_fetch(db, high=high)
                    log.info(
                        "bolha lookahead: batch anchor=%s high_water=%s",
                        anchor,
                        high,
                    )

                    batch_resolved = False
                    for k in range(1, LOOKAHEAD_ADS + 1):
                        ad_id = anchor + k
                        url = AD_PROBE_URL_TEMPLATE.format(ad_id=ad_id)
                        now = datetime.now(timezone.utc)
                        try:
                            resp = await probe.get(url)
                        except httpx.HTTPError as e:
                            log.warning(
                                "bolha lookahead: probe %s failed: %s", ad_id, e
                            )
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
                        await record_bolha_ad_scrape_from_outcome(
                            db,
                            ad_id,
                            source=self.name,
                            outcome=oc,
                            fetched_at=now,
                            http_status=http_st,
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
                            try:
                                inserted = await upsert_items(
                                    db, LISTING_SOURCE, [item]
                                )
                            except Exception:
                                log.exception(
                                    "bolha lookahead: upsert failed for ad_id=%s",
                                    ad_id,
                                )
                                inserted = 0

                            self._cached_db_max = max(
                                self._cached_db_max or 0, ad_id
                            )
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
        finally:
            await probe.aclose()
