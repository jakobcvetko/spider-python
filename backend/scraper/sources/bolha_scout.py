from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal
from app.scraper_events import make_event
from scraper.base import ScrapedItem
from scraper.sources.bolha_common import (
    EmitFn,
    IAPI_HOME_URL,
    LISTING_SOURCE,
    SCOUT_GALLOP_STEP,
    SCOUT_MAX_ID_SPAN,
    SCOUT_MAX_PROBES,
    SCOUT_PROBE_DELAY_SECONDS,
    SCOUT_PROBE_TIMEOUT_SECONDS,
    SCOUT_REFINE_STEP,
    ProbeKind,
    get_meta,
    is_known_probe_kind,
    max_ad_id_from_homepage_html,
    max_numeric_listing_id,
    meta_begin_fetch,
    meta_set_homepage_max,
    meta_set_last_working,
    probe_ad_id,
)

log = logging.getLogger(__name__)


def _probe_client(shared: httpx.AsyncClient) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers=dict(shared.headers),
        follow_redirects=True,
        timeout=httpx.Timeout(SCOUT_PROBE_TIMEOUT_SECONDS),
        limits=httpx.Limits(max_keepalive_connections=8, max_connections=16),
    )


@dataclass
class _ScoutState:
    lo: int
    hi: int
    high_water: int
    probe_count: int = 0


class BolhaScoutSource:
    name = "bolha.scout"
    listing_source = LISTING_SOURCE

    async def fetch(
        self,
        client: httpx.AsyncClient,
        emit: EmitFn = None,
    ) -> list[ScrapedItem]:
        probe = _probe_client(client)
        try:
            async with SessionLocal() as db:
                return await self._run_scout(db, probe, emit)
        finally:
            await probe.aclose()

    async def _run_scout(
        self,
        db: AsyncSession,
        probe: httpx.AsyncClient,
        emit: EmitFn,
    ) -> list[ScrapedItem]:
        meta = await get_meta(db)
        meta_anchor = int(meta.last_working_ad_id or 0)

        hp_max = 0
        try:
            home = await probe.get(IAPI_HOME_URL, timeout=SCOUT_PROBE_TIMEOUT_SECONDS)
            if home.status_code == 200:
                hp_max = max_ad_id_from_homepage_html(home.text)
                await meta_set_homepage_max(db, hp_max)
        except httpx.HTTPError as e:
            log.warning("bolha scout: homepage fetch failed: %s", e)

        db_max = await max_numeric_listing_id(db)
        seed = max(hp_max, db_max, meta_anchor)
        high_water = seed

        await meta_begin_fetch(db, high=high_water)

        state = _ScoutState(lo=seed, hi=seed + 1, high_water=high_water)
        log.info(
            "bolha scout: seed lo=%s (homepage=%s db=%s meta=%s)",
            seed,
            hp_max,
            db_max,
            meta_anchor,
        )

        kind = await self._probe(db, probe, emit, state, seed)
        if kind is None:
            await db.commit()
            raise RuntimeError(f"bolha scout: cannot probe seed id {seed}")

        if not is_known_probe_kind(kind):
            log.info(
                "bolha scout: seed %s is %s; searching downward for last known id",
                seed,
                kind,
            )
            lo_known = await self._binary_search_known(
                db, probe, emit, state, lo=0, hi=seed
            )
            if lo_known <= 0:
                await db.commit()
                raise RuntimeError(
                    f"bolha scout: no known id below seed {seed} (got {kind})"
                )
            state.lo = lo_known
            state.hi = seed
        else:
            state.lo = seed

        if not await self._gallop_up(db, probe, emit, state):
            await db.commit()
            raise RuntimeError("bolha scout: gallop exceeded safety limits")

        await self._refine_up(db, probe, emit, state)
        await self._binary_search_known(
            db, probe, emit, state, lo=state.lo, hi=state.hi
        )

        new_anchor = state.lo
        if new_anchor > meta_anchor:
            await meta_set_last_working(db, new_anchor)
            log.info(
                "bolha scout: advanced last_working %s -> %s (%s probes)",
                meta_anchor,
                new_anchor,
                state.probe_count,
            )
        else:
            log.info(
                "bolha scout: last_working unchanged at %s (%s probes)",
                meta_anchor,
                state.probe_count,
            )

        await db.commit()

        if emit is not None:
            await emit(
                make_event(
                    "bolha_scout_done",
                    source=self.name,
                    message=(
                        f"scout done: last_working {new_anchor} "
                        f"(was {meta_anchor}), {state.probe_count} probes"
                    ),
                    data={
                        "old_anchor": meta_anchor,
                        "new_anchor": new_anchor,
                        "probes": state.probe_count,
                        "homepage_max": hp_max,
                        "db_max": db_max,
                        "seed": seed,
                    },
                )
            )

        return []

    async def _probe(
        self,
        db: AsyncSession,
        probe: httpx.AsyncClient,
        emit: EmitFn,
        state: _ScoutState,
        ad_id: int,
    ) -> ProbeKind | None:
        if state.probe_count >= SCOUT_MAX_PROBES:
            return None
        state.probe_count += 1
        if state.probe_count > 1:
            await asyncio.sleep(SCOUT_PROBE_DELAY_SECONDS)
        kind = await probe_ad_id(
            probe,
            db,
            ad_id,
            source_name=self.name,
            emit=emit,
            last_working_ad_id=state.lo,
            high_water=state.high_water,
        )
        return kind

    async def _gallop_up(
        self,
        db: AsyncSession,
        probe: httpx.AsyncClient,
        emit: EmitFn,
        state: _ScoutState,
    ) -> bool:
        step = SCOUT_GALLOP_STEP
        seed_lo = state.lo
        while True:
            if state.lo - seed_lo > SCOUT_MAX_ID_SPAN:
                log.error(
                    "bolha scout: exceeded max id span %s above seed %s",
                    SCOUT_MAX_ID_SPAN,
                    seed_lo,
                )
                return False
            candidate = state.lo + step
            kind = await self._probe(db, probe, emit, state, candidate)
            if kind is None:
                return False
            if is_known_probe_kind(kind):
                state.lo = candidate
                step = min(step * 2, SCOUT_MAX_ID_SPAN)
                continue
            state.hi = candidate
            log.info(
                "bolha scout: gallop bracket [%s, %s] (first unknown at %s)",
                state.lo,
                state.hi,
                candidate,
            )
            return True

    async def _refine_up(
        self,
        db: AsyncSession,
        probe: httpx.AsyncClient,
        emit: EmitFn,
        state: _ScoutState,
    ) -> None:
        while state.hi - state.lo > SCOUT_REFINE_STEP:
            candidate = state.lo + SCOUT_REFINE_STEP
            kind = await self._probe(db, probe, emit, state, candidate)
            if kind is None:
                return
            if is_known_probe_kind(kind):
                state.lo = candidate
            else:
                state.hi = candidate
                return

    async def _binary_search_known(
        self,
        db: AsyncSession,
        probe: httpx.AsyncClient,
        emit: EmitFn,
        state: _ScoutState,
        *,
        lo: int,
        hi: int,
    ) -> int:
        """Return highest known id in (lo, hi]; updates state.lo."""
        while hi - lo > 1:
            mid = (lo + hi) // 2
            kind = await self._probe(db, probe, emit, state, mid)
            if kind is None:
                break
            if is_known_probe_kind(kind):
                lo = mid
            else:
                hi = mid
        state.lo = lo
        state.hi = hi
        return lo
