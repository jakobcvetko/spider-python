"""avto.net ID lookahead — parallel probes in a fixed band ahead of last_working."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import NoReturn

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.database import SessionLocal
from scraper.sources.avto_net_common import LISTING_SOURCE, LOOKAHEAD_ADS
from scraper.sources.avto_net_probe import ProbeResult, probe_ad_id as fetch_probe
from scraper.sources.avto_net_scout import run_avtonet_scout
from scraper.sources.avtonet_pipeline import (
    EmitFn,
    LOOKAHEAD_HIGH_WATER_REFRESH_BATCHES,
    LOOKAHEAD_SCOUT_IDLE_SECONDS,
    LOOKAHEAD_TIMEOUT_SECONDS,
    activate_last_working_ad,
    emit_progress_tick,
    get_meta,
    max_numeric_listing_id,
    meta_begin_fetch,
    meta_set_last_working,
    outcome_from_class,
    pipeline_kind_from_probe,
    record_avtonet_ad_scrape,
    record_avtonet_ad_scrape_from_outcome,
)

log = logging.getLogger(__name__)

SOURCE_NAME = "avto.net.lookahead"


@dataclass
class _ProbeSlot:
    ad_id: int
    result: ProbeResult | None = None
    http_error: str | None = None


class AvtoNetLookaheadSource:
    name = SOURCE_NAME
    listing_source = LISTING_SOURCE

    def __init__(self) -> None:
        self._batch_count = 0
        self._cached_db_max: int | None = None

    async def _refresh_high_water(
        self,
        db: AsyncSession,
        *,
        meta_anchor: int,
    ) -> int:
        self._batch_count += 1
        refresh_db = (
            self._cached_db_max is None
            or self._batch_count % LOOKAHEAD_HIGH_WATER_REFRESH_BATCHES == 0
            or meta_anchor >= (self._cached_db_max or 0)
        )
        if refresh_db:
            self._cached_db_max = await max_numeric_listing_id(db)
        return max(meta_anchor, self._cached_db_max or 0)

    async def _probe_parallel(
        self,
        client: httpx.AsyncClient,
        ad_ids: list[int],
        *,
        settings: Settings,
        emit: EmitFn,
    ) -> list[_ProbeSlot]:
        async def _one(ad_id: int) -> _ProbeSlot:
            result = await fetch_probe(
                client,
                ad_id,
                settings=settings,
                emit=emit,
                source=self.name,
            )
            if result.http_status < 0:
                log.warning(
                    "avto.net lookahead: probe %s failed: %s",
                    ad_id,
                    result.detail,
                )
                return _ProbeSlot(
                    ad_id=ad_id, http_error=result.detail or "http_error"
                )
            return _ProbeSlot(ad_id=ad_id, result=result)

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
        await record_avtonet_ad_scrape(
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
        )

    async def _process_probe_batch(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        *,
        anchor: int,
        high: int,
        batch_size: int,
        settings: Settings,
        emit: EmitFn,
    ) -> tuple[bool, bool]:
        """Probe anchor+1..anchor+batch_size in parallel.

        Returns ``(batch_resolved, found_active)``.
        """
        ad_ids = [anchor + k for k in range(1, batch_size + 1)]
        slots = await self._probe_parallel(
            client, ad_ids, settings=settings, emit=emit
        )
        slots.sort(key=lambda s: s.ad_id)
        now = datetime.now(timezone.utc)

        for slot in slots:
            if slot.http_error is not None:
                await self._persist_http_error(
                    db, slot, anchor=anchor, high=high, now=now, emit=emit
                )
                continue

            assert slot.result is not None
            result = slot.result
            kind = pipeline_kind_from_probe(result)
            oc = outcome_from_class(kind)

            await record_avtonet_ad_scrape_from_outcome(
                db,
                slot.ad_id,
                source=self.name,
                outcome=oc,
                fetched_at=now,
                http_status=result.http_status,
                detail=result.detail,
                emit=emit,
            )

            if kind == "active" and result.item is not None:
                await emit_progress_tick(
                    emit,
                    scraper_name=self.name,
                    ad_id=slot.ad_id,
                    last_working_ad_id=anchor,
                    high_water=high,
                    outcome=oc,
                    http_status=result.http_status,
                )
                inserted = await activate_last_working_ad(
                    db,
                    slot.ad_id,
                    item=result.item,
                    source=self.name,
                    emit=emit,
                    now=now,
                )
                self._cached_db_max = max(self._cached_db_max or 0, slot.ad_id)
                log.info(
                    "avto.net lookahead: active ad_id=%s (anchor was %s), inserted=%s",
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
                    http_status=result.http_status,
                )
                await meta_set_last_working(db, slot.ad_id)
                await db.commit()
                log.info(
                    "avto.net lookahead: expired ad_id=%s (anchor was %s), "
                    "advanced last_working, no backfill",
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
                http_status=result.http_status,
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
            return last_active_at
        log.info(
            "avto.net lookahead: no new active ad for %.0fs (>= %.0fs), running scout",
            idle_for,
            scout_idle_seconds,
        )
        try:
            await run_avtonet_scout(db, client, emit)
        except RuntimeError:
            log.exception(
                "avto.net lookahead: idle scout failed; continuing with stored anchor"
            )
        return time.monotonic()

    async def fetch(
        self,
        client: httpx.AsyncClient,
        emit: EmitFn = None,
    ) -> NoReturn:
        settings = get_settings()
        batch_size = settings.avtonet_lookahead_batch_size or LOOKAHEAD_ADS
        scout_idle_seconds = (
            settings.avtonet_lookahead_scout_idle_seconds
            or LOOKAHEAD_SCOUT_IDLE_SECONDS
        )
        try:
            async with SessionLocal() as db:
                log.info("avto.net lookahead: running initial scout")
                try:
                    await run_avtonet_scout(db, client, emit)
                except RuntimeError:
                    log.exception(
                        "avto.net lookahead: initial scout failed; "
                        "continuing with stored anchor"
                    )
                last_active_at = time.monotonic()

                while True:
                    meta = await get_meta(db)
                    anchor = int(meta.last_working_ad_id or 0)
                    high = await self._refresh_high_water(db, meta_anchor=anchor)

                    await meta_begin_fetch(db, high=high)
                    log.info(
                        "avto.net lookahead: parallel batch anchor=%s "
                        "ids=%s..%s high_water=%s",
                        anchor,
                        anchor + 1,
                        anchor + batch_size,
                        high,
                    )

                    batch_resolved, found_active = await self._process_probe_batch(
                        db,
                        client,
                        anchor=anchor,
                        high=high,
                        batch_size=batch_size,
                        settings=settings,
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
            pass


async def _run_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Probe avto.net detail URLs (parallel lookahead band).",
    )
    parser.add_argument("--loop", action="store_true")
    args = parser.parse_args(argv)
    settings = get_settings()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    headers = {
        "User-Agent": settings.scraper_user_agent,
        "Accept-Language": "sl,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml",
    }

    async with httpx.AsyncClient(
        headers=headers,
        follow_redirects=True,
        timeout=httpx.Timeout(30.0),
    ) as client:
        source = AvtoNetLookaheadSource()
        if args.loop:
            await source.fetch(client)
            return 0
        log.warning("Single-batch CLI removed; use --loop or make avtonet:lookahead")
        return 1


def main(argv: list[str] | None = None) -> None:
    raise SystemExit(asyncio.run(_run_cli(argv if argv is not None else sys.argv[1:])))


if __name__ == "__main__":
    main()
