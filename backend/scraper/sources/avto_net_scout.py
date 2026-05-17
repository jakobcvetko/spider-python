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
    SCOUT_REFINE_STEP,
)
from scraper.sources.avtonet_registry import (
    AvtonetProbeOutcome,
    EmitFn,
    get_meta,
    max_numeric_listing_id,
    meta_begin_batch,
    meta_set_last_working,
    scout_probe_ad_id,
)

log = logging.getLogger(__name__)


@dataclass
class _ScoutState:
    lo: int
    hi: int
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

        await meta_begin_batch(db)

        state = _ScoutState(lo=seed, hi=seed + 1)
        log.info(
            "avto.net scout: seed lo=%s (db=%s meta=%s config=%s)",
            seed,
            db_max,
            meta_anchor,
            settings.avtonet_lookahead_start_id,
        )

        seed_outcome = await self._probe(db, client, emit, state, seed)
        if seed_outcome is None:
            await db.commit()
            raise RuntimeError(f"avto.net scout: cannot probe seed id {seed}")

        if not seed_outcome.confirmed:
            log.info(
                "avto.net scout: seed %s is empty (%s); searching downward for last known id",
                seed,
                seed_outcome.scrape_result,
            )
            lo_known = await self._binary_search_known(
                db, client, emit, state, lo=0, hi=seed
            )
            if lo_known <= 0:
                await db.commit()
                raise RuntimeError(
                    f"avto.net scout: no known id below seed {seed} "
                    f"(got {seed_outcome.scrape_result})"
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
            await meta_set_last_working(db, new_anchor)
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
    ) -> AvtonetProbeOutcome | None:
        if state.probe_count >= SCOUT_MAX_PROBES:
            return None
        state.probe_count += 1
        if state.probe_count > 1:
            await asyncio.sleep(SCOUT_PROBE_DELAY_SECONDS)
        return await scout_probe_ad_id(
            client,
            db,
            ad_id,
            source_name=self.name,
            emit=emit,
            last_working_ad_id=state.lo,
        )

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
            outcome = await self._probe(db, client, emit, state, candidate)
            if outcome is None:
                return False
            if outcome.confirmed:
                state.lo = candidate
                step = min(step * 2, SCOUT_MAX_ID_SPAN)
                continue
            state.hi = candidate
            log.info(
                "avto.net scout: gallop bracket [%s, %s] (first empty at %s)",
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
            outcome = await self._probe(db, client, emit, state, candidate)
            if outcome is None:
                return
            if outcome.confirmed:
                state.lo = candidate
            else:
                state.hi = candidate
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
            outcome = await self._probe(db, client, emit, state, mid)
            if outcome is None:
                break
            if outcome.confirmed:
                lo = mid
            else:
                hi = mid
        state.lo = lo
        state.hi = hi
        return lo
