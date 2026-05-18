from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import NoReturn

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import SessionLocal
from scraper.sources.bolha_scout import run_bolha_scout
from scraper.http_retries import httpx_get_with_retries
from scraper.sources.bolha_common import (
    EmitFn,
    IAPI_HOME_URL,
    SCOUT_HTTP_RETRIES,
    activate_last_working_ad,
    make_probe_client,
    LISTING_SOURCE,
    LOOKAHEAD_ADS,
    LOOKAHEAD_HIGH_WATER_REFRESH_BATCHES,
    LOOKAHEAD_HOMEPAGE_REFRESH_BATCHES,
    LOOKAHEAD_PROBE_TIMEOUT_SECONDS,
    LOOKAHEAD_SCOUT_IDLE_SECONDS,
    LOOKAHEAD_TIMEOUT_SECONDS,
    classify_probe_response,
    emit_progress_tick,
    fetch_probe_http,
    get_meta,
    max_ad_id_from_homepage_html,
    max_numeric_listing_id,
    meta_begin_fetch,
    meta_set_homepage_max,
    meta_set_last_working,
    outcome_from_class,
    record_bolha_ad_scrape,
    record_bolha_ad_scrape_from_outcome,
)

log = logging.getLogger(__name__)


@dataclass
class _ProbeSlot:
    ad_id: int
    resp: httpx.Response | None = None
    html: str | None = None
    http_error: str | None = None


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
                home = await httpx_get_with_retries(
                    probe,
                    IAPI_HOME_URL,
                    timeout=LOOKAHEAD_PROBE_TIMEOUT_SECONDS,
                    max_attempts=SCOUT_HTTP_RETRIES,
                )
                if home.status_code == 200:
                    hp_max = max_ad_id_from_homepage_html(home.text)
                    await meta_set_homepage_max(db, hp_max)
                    high = max(high, hp_max)
            except httpx.HTTPError as e:
                log.warning("bolha lookahead: periodic homepage refresh failed: %s", e)

        return high

    async def _probe_parallel(
        self,
        probe: httpx.AsyncClient,
        ad_ids: list[int],
    ) -> list[_ProbeSlot]:
        async def _one(ad_id: int) -> _ProbeSlot:
            fetch = await fetch_probe_http(probe, ad_id)
            if fetch.http_error is not None:
                log.warning("bolha lookahead: probe %s failed: %s", ad_id, fetch.http_error)
                return _ProbeSlot(ad_id=ad_id, http_error=fetch.http_error)
            assert fetch.resp is not None
            return _ProbeSlot(
                ad_id=ad_id, resp=fetch.resp, html=fetch.resp.text
            )

        return list(await asyncio.gather(*[_one(ad_id) for ad_id in ad_ids]))

    async def _persist_http_error(
        self,
        db: AsyncSession,
        slot: _ProbeSlot,
        *,
        anchor: int,
        high: int,
        now: datetime,
        emit: EmitFn,
    ) -> None:
        detail = (slot.http_error or "unknown")[:500]
        await record_bolha_ad_scrape(
            db,
            slot.ad_id,
            source=self.name,
            result="error",
            fetched_at=now,
            http_status=-1,
            detail=detail,
            emit=emit,
        )
        await emit_progress_tick(
            emit,
            scraper_name=self.name,
            ad_id=slot.ad_id,
            last_working_ad_id=anchor,
            high_water=high,
            outcome="http_error",
            http_status=-1,
            gtm_ad_status=None,
        )

    async def _process_probe_batch(
        self,
        db: AsyncSession,
        probe: httpx.AsyncClient,
        *,
        anchor: int,
        high: int,
        batch_size: int,
        emit: EmitFn,
    ) -> tuple[bool, bool]:
        """Probe anchor+1..anchor+batch_size in parallel.

        Returns ``(batch_resolved, found_active)``.
        """
        ad_ids = [anchor + k for k in range(1, batch_size + 1)]
        slots = await self._probe_parallel(probe, ad_ids)
        slots.sort(key=lambda s: s.ad_id)
        now = datetime.now(timezone.utc)

        for slot in slots:
            if slot.http_error is not None:
                await self._persist_http_error(
                    db, slot, anchor=anchor, high=high, now=now, emit=emit
                )
                continue

            assert slot.resp is not None and slot.html is not None
            kind, gtm, _detail, http_st = classify_probe_response(
                slot.resp, slot.html, ad_id=slot.ad_id
            )
            oc = outcome_from_class(kind)

            await record_bolha_ad_scrape_from_outcome(
                db,
                slot.ad_id,
                source=self.name,
                outcome=oc,
                fetched_at=now,
                http_status=http_st,
                emit=emit,
            )

            if kind == "active":
                await emit_progress_tick(
                    emit,
                    scraper_name=self.name,
                    ad_id=slot.ad_id,
                    last_working_ad_id=anchor,
                    high_water=high,
                    outcome=oc,
                    http_status=http_st,
                    gtm_ad_status=gtm,
                )
                inserted = await activate_last_working_ad(
                    db,
                    slot.ad_id,
                    html=slot.html,
                    source=self.name,
                    emit=emit,
                    now=now,
                )
                self._cached_db_max = max(self._cached_db_max or 0, slot.ad_id)
                log.info(
                    "bolha lookahead: active ad_id=%s (anchor was %s), inserted=%s",
                    slot.ad_id,
                    anchor,
                    inserted,
                )
                await db.commit()
                return True, True

            if kind == "expired":
                await emit_progress_tick(
                    emit,
                    scraper_name=self.name,
                    ad_id=slot.ad_id,
                    last_working_ad_id=slot.ad_id,
                    high_water=high,
                    outcome=oc,
                    http_status=http_st,
                    gtm_ad_status=gtm,
                )
                await meta_set_last_working(db, slot.ad_id)
                await db.commit()
                log.info(
                    "bolha lookahead: expired (redirect inactive) ad_id=%s "
                    "(anchor was %s), advanced last_working, no backfill",
                    slot.ad_id,
                    anchor,
                )
                return True, False

            await emit_progress_tick(
                emit,
                scraper_name=self.name,
                ad_id=slot.ad_id,
                last_working_ad_id=anchor,
                high_water=high,
                outcome=oc,
                http_status=http_st,
                gtm_ad_status=gtm,
            )

        return False, False

    async def _run_scout_if_idle(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        emit: EmitFn,
        *,
        last_active_at: float,
        scout_idle_seconds: float,
    ) -> float:
        idle_for = time.monotonic() - last_active_at
        if idle_for < scout_idle_seconds:
            log.debug(
                "bolha lookahead: %.0fs since last active (scout at %.0fs)",
                idle_for,
                scout_idle_seconds,
            )
            return last_active_at
        log.info(
            "bolha lookahead: no new active ad for %.0fs (>= %.0fs), running scout",
            idle_for,
            scout_idle_seconds,
        )
        try:
            await run_bolha_scout(db, client, emit)
        except RuntimeError:
            log.exception(
                "bolha lookahead: idle scout failed; continuing with stored anchor"
            )
        return time.monotonic()

    async def fetch(
        self,
        client: httpx.AsyncClient,
        emit: EmitFn = None,
    ) -> NoReturn:
        """Runs until process exit (worker uses no interval job for this source)."""
        settings = get_settings()
        raw_idle = settings.bolha_lookahead_scout_idle_seconds
        scout_idle_seconds = (
            raw_idle if raw_idle > 0 else LOOKAHEAD_SCOUT_IDLE_SECONDS
        )
        probe = make_probe_client(client, timeout_seconds=LOOKAHEAD_PROBE_TIMEOUT_SECONDS)
        batch_size = LOOKAHEAD_ADS
        try:
            async with SessionLocal() as db:
                log.info(
                    "bolha lookahead: scout idle threshold=%.0fs "
                    "(BOLHA_LOOKAHEAD_SCOUT_IDLE_SECONDS=%s)",
                    scout_idle_seconds,
                    raw_idle,
                )
                log.info("bolha lookahead: running initial scout")
                try:
                    await run_bolha_scout(db, client, emit)
                except RuntimeError:
                    log.exception(
                        "bolha lookahead: initial scout failed; "
                        "continuing with stored anchor"
                    )
                last_active_at = time.monotonic()

                while True:
                    meta = await get_meta(db)
                    anchor = int(meta.last_working_ad_id or 0)
                    high = await self._refresh_high_water(
                        db, probe, meta_anchor=anchor
                    )

                    await meta_begin_fetch(db, high=high)
                    log.info(
                        "bolha lookahead: parallel batch anchor=%s "
                        "ids=%s..%s high_water=%s",
                        anchor,
                        anchor + 1,
                        anchor + batch_size,
                        high,
                    )

                    batch_resolved, found_active = await self._process_probe_batch(
                        db,
                        probe,
                        anchor=anchor,
                        high=high,
                        batch_size=batch_size,
                        emit=emit,
                    )

                    if found_active:
                        last_active_at = time.monotonic()
                    else:
                        last_active_at = await self._run_scout_if_idle(
                            db,
                            client,
                            emit,
                            last_active_at=last_active_at,
                            scout_idle_seconds=scout_idle_seconds,
                        )

                    if not batch_resolved:
                        await db.commit()
                        await asyncio.sleep(LOOKAHEAD_TIMEOUT_SECONDS)
        finally:
            await probe.aclose()
