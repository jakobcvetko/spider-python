from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import SessionLocal
from app.scraper_events import make_event
from scraper.base import ScrapedItem
from scraper.sources.avto_net_common import (
    LISTING_SOURCE,
    SCOUT_GALLOP_STEP,
    SCOUT_MAX_ID_SPAN,
    SCOUT_MAX_PROBES,
    SCOUT_PROBE_DELAY_SECONDS,
    LOOKAHEAD_ADS,
    SCOUT_PROBE_WINDOW_RADIUS,
    SCOUT_REFINE_STEP,
)
from scraper.sources.avto_net_probe import probe_ad_id as fetch_probe
from scraper.sources.avtonet_pipeline import (
    EmitFn,
    PipelineKind,
    finalize_scout_last_working_advance,
    get_meta,
    is_known_probe_kind,
    max_numeric_listing_id,
    meta_begin_fetch,
    persist_probe_result,
    probe_ad_id,
)

log = logging.getLogger(__name__)


@dataclass
class _ScoutState:
    lo: int
    hi: int
    high_water: int
    probe_count: int = 0


async def run_avtonet_scout(
    db: AsyncSession,
    client: httpx.AsyncClient,
    emit: EmitFn = None,
) -> None:
    """Gallop + binary search to refresh ``last_working_ad_id`` before lookahead."""
    scout = AvtoNetScoutSource()
    await scout._run_scout(db, client, emit)


class AvtoNetScoutSource:
    name = "avto.net.scout"
    listing_source = LISTING_SOURCE

    async def fetch(
        self,
        client: httpx.AsyncClient,
        emit: EmitFn = None,
    ) -> list[ScrapedItem]:
        async with SessionLocal() as db:
            await run_avtonet_scout(db, client, emit)
        return []

    async def _run_scout(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        emit: EmitFn,
    ) -> list[ScrapedItem]:
        settings = get_settings()
        meta = await get_meta(db)
        meta_anchor = int(meta.last_working_ad_id or 0)

        db_max = await max_numeric_listing_id(db)
        seed = max(db_max, meta_anchor, settings.avtonet_lookahead_start_id)
        high_water = seed

        await meta_begin_fetch(db, high=high_water)

        state = _ScoutState(lo=seed, hi=seed + 1, high_water=high_water)
        log.info(
            "avto.net scout: seed lo=%s (db=%s meta=%s config=%s)",
            seed,
            db_max,
            meta_anchor,
            settings.avtonet_lookahead_start_id,
        )

        kind = await self._probe(db, client, emit, state, seed)
        if kind is None:
            await db.commit()
            raise RuntimeError(f"avto.net scout: cannot probe seed id {seed}")

        if not is_known_probe_kind(kind):
            log.info(
                "avto.net scout: seed %s is %s; searching downward for last known id",
                seed,
                kind,
            )
            lo_known = await self._binary_search_known(
                db, client, emit, state, lo=0, hi=seed
            )
            if lo_known <= 0:
                await db.commit()
                raise RuntimeError(
                    f"avto.net scout: no known id below seed {seed} (got {kind})"
                )
            state.lo = lo_known
            state.hi = seed
        else:
            state.lo = seed

        if not await self._gallop_up(db, client, emit, state):
            await db.commit()
            raise RuntimeError("avto.net scout: gallop exceeded safety limits")

        await self._refine_up(db, client, emit, state)
        await self._binary_search_known(
            db, client, emit, state, lo=state.lo, hi=state.hi
        )

        new_anchor = state.lo
        if new_anchor > meta_anchor:
            await finalize_scout_last_working_advance(
                db,
                client,
                new_anchor,
                source_name=self.name,
                emit=emit,
                settings=settings,
            )
            log.info(
                "avto.net scout: advanced last_working %s -> %s (%s probes)",
                meta_anchor,
                new_anchor,
                state.probe_count,
            )
        else:
            log.info(
                "avto.net scout: last_working unchanged at %s (%s probes)",
                meta_anchor,
                state.probe_count,
            )

        await db.commit()

        if emit is not None:
            await emit(
                make_event(
                    "avtonet_scout_done",
                    source=self.name,
                    message=(
                        f"scout done: last_working {new_anchor} "
                        f"(was {meta_anchor}), {state.probe_count} probes"
                    ),
                    data={
                        "old_anchor": meta_anchor,
                        "new_anchor": new_anchor,
                        "probes": state.probe_count,
                        "db_max": db_max,
                        "seed": seed,
                    },
                )
            )

        return []

    async def _probe(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        emit: EmitFn,
        state: _ScoutState,
        ad_id: int,
        *,
        in_batch: bool = False,
    ) -> PipelineKind | None:
        if state.probe_count >= SCOUT_MAX_PROBES:
            return None
        state.probe_count += 1
        if not in_batch and state.probe_count > 1:
            await asyncio.sleep(SCOUT_PROBE_DELAY_SECONDS)
        settings = get_settings()
        return await probe_ad_id(
            client,
            db,
            ad_id,
            source_name=self.name,
            emit=emit,
            last_working_ad_id=state.lo,
            high_water=state.high_water,
            settings=settings,
        )

    async def _probe_window(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        emit: EmitFn,
        state: _ScoutState,
        center: int,
    ) -> tuple[int | None, bool]:
        """Probe a LOOKAHEAD_ADS-wide window around *center* in parallel.

        Returns (highest_known_id, budget_exhausted). ``highest_known_id`` is None
        when no active/expired listing exists in the window.
        """
        half_low = LOOKAHEAD_ADS // 2
        ad_ids = [
            center + offset
            for offset in range(-half_low, LOOKAHEAD_ADS - half_low)
            if center + offset > 0
        ]
        n = len(ad_ids)
        if state.probe_count + n > SCOUT_MAX_PROBES:
            return None, True
        if state.probe_count > 0:
            await asyncio.sleep(SCOUT_PROBE_DELAY_SECONDS)
        state.probe_count += n

        settings = get_settings()
        fetched = await asyncio.gather(
            *[
                fetch_probe(
                    client,
                    ad_id,
                    settings=settings,
                    emit=emit,
                    source=self.name,
                )
                for ad_id in ad_ids
            ]
        )
        results: list[tuple[int, PipelineKind | None]] = []
        for result in sorted(fetched, key=lambda r: r.ad_id):
            kind = await persist_probe_result(
                db,
                result,
                source_name=self.name,
                emit=emit,
                last_working_ad_id=state.lo,
                high_water=state.high_water,
            )
            results.append((result.ad_id, kind))
        exhausted = any(kind is None for _, kind in results)
        known_ids = [
            ad_id
            for ad_id, kind in results
            if kind is not None and is_known_probe_kind(kind)
        ]
        if known_ids:
            return max(known_ids), exhausted
        return None, exhausted

    async def _gallop_up(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        emit: EmitFn,
        state: _ScoutState,
    ) -> bool:
        step = SCOUT_GALLOP_STEP
        seed_lo = state.lo
        while True:
            if state.lo - seed_lo > SCOUT_MAX_ID_SPAN:
                log.error(
                    "avto.net scout: exceeded max id span %s above seed %s",
                    SCOUT_MAX_ID_SPAN,
                    seed_lo,
                )
                return False
            candidate = state.lo + step
            highest_known, exhausted = await self._probe_window(
                db, client, emit, state, candidate
            )
            if exhausted:
                return False
            if highest_known is not None:
                state.lo = highest_known
                step = min(step * 2, SCOUT_MAX_ID_SPAN)
                continue
            state.hi = candidate + SCOUT_PROBE_WINDOW_RADIUS
            log.info(
                "avto.net scout: gallop bracket [%s, %s] "
                "(no known in window around %s)",
                state.lo,
                state.hi,
                candidate,
            )
            return True

    async def _refine_up(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        emit: EmitFn,
        state: _ScoutState,
    ) -> None:
        while state.hi - state.lo > SCOUT_REFINE_STEP:
            candidate = state.lo + SCOUT_REFINE_STEP
            highest_known, exhausted = await self._probe_window(
                db, client, emit, state, candidate
            )
            if exhausted:
                return
            if highest_known is not None:
                state.lo = highest_known
            else:
                state.hi = candidate + SCOUT_PROBE_WINDOW_RADIUS
                return

    async def _binary_search_known(
        self,
        db: AsyncSession,
        client: httpx.AsyncClient,
        emit: EmitFn,
        state: _ScoutState,
        *,
        lo: int,
        hi: int,
    ) -> int:
        while hi - lo > 1:
            mid = (lo + hi) // 2
            highest_known, exhausted = await self._probe_window(
                db, client, emit, state, mid
            )
            if exhausted:
                break
            if highest_known is not None:
                lo = highest_known
            else:
                hi = max(lo + 1, mid - SCOUT_PROBE_WINDOW_RADIUS - 1)
        state.lo = lo
        state.hi = hi
        return lo
