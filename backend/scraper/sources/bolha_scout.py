from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal
from app.scraper_events import make_event
from scraper.base import ScrapedItem
from scraper.http_retries import httpx_get_with_retries
from scraper.sources.bolha_common import (
    EmitFn,
    IAPI_HOME_URL,
    LISTING_SOURCE,
    SCOUT_GALLOP_STEP,
    SCOUT_MAX_ID_SPAN,
    SCOUT_MAX_PROBES,
    SCOUT_PROBE_DELAY_SECONDS,
    SCOUT_PROBE_TIMEOUT_SECONDS,
    LOOKAHEAD_ADS,
    SCOUT_PROBE_WINDOW_RADIUS,
    SCOUT_REFINE_STEP,
    SCOUT_HTTP_RETRIES,
    ProbeKind,
    fetch_probe_http,
    finalize_scout_last_working_advance,
    get_meta,
    make_probe_client,
    is_known_probe_kind,
    max_ad_id_from_homepage_html,
    max_numeric_listing_id,
    meta_begin_fetch,
    meta_set_homepage_max,
    persist_probe_fetch,
    probe_ad_id,
)

log = logging.getLogger(__name__)


def _window_ad_ids(center: int) -> list[int]:
    half_low = LOOKAHEAD_ADS // 2
    return [
        center + offset
        for offset in range(-half_low, LOOKAHEAD_ADS - half_low)
        if center + offset > 0
    ]


def _format_window_outcomes(
    results: list[tuple[int, ProbeKind | None]],
) -> str:
    parts: list[str] = []
    for ad_id, kind in results:
        label = "err" if kind is None else kind
        parts.append(f"{ad_id}:{label}")
    return "[" + ", ".join(parts) + "]"


@dataclass
class _ScoutState:
    lo: int
    hi: int
    high_water: int
    probe_count: int = 0


async def run_bolha_scout(
    db: AsyncSession,
    shared: httpx.AsyncClient,
    emit: EmitFn = None,
) -> None:
    """Gallop + binary search to refresh ``last_working_ad_id`` before lookahead."""
    scout = BolhaScoutSource()
    probe = make_probe_client(shared, timeout_seconds=SCOUT_PROBE_TIMEOUT_SECONDS)
    try:
        await scout._run_scout(db, probe, emit)
    finally:
        await probe.aclose()


class BolhaScoutSource:
    name = "bolha.scout"
    listing_source = LISTING_SOURCE

    async def fetch(
        self,
        client: httpx.AsyncClient,
        emit: EmitFn = None,
    ) -> list[ScrapedItem]:
        async with SessionLocal() as db:
            await run_bolha_scout(db, client, emit)
        return []

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
            home = await httpx_get_with_retries(
                probe,
                IAPI_HOME_URL,
                timeout=SCOUT_PROBE_TIMEOUT_SECONDS,
                max_attempts=SCOUT_HTTP_RETRIES,
            )
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
        log.debug(
            "bolha scout: start meta_anchor=%s db_max=%s hp_max=%s seed=%s "
            "high_water=%s max_probes=%s window_size=%s",
            meta_anchor,
            db_max,
            hp_max,
            seed,
            high_water,
            SCOUT_MAX_PROBES,
            LOOKAHEAD_ADS,
        )

        kind = await self._probe(db, probe, emit, state, seed)
        log.debug(
            "bolha scout: seed probe ad_id=%s kind=%s probes=%s",
            seed,
            kind,
            state.probe_count,
        )
        if kind is None:
            await db.commit()
            raise RuntimeError(f"bolha scout: cannot probe seed id {seed}")

        if not is_known_probe_kind(kind):
            log.info(
                "bolha scout: seed %s is %s; searching downward for last known id",
                seed,
                kind,
            )
            log.debug(
                "bolha scout: phase=binary_search_downward lo=0 hi=%s probes=%s",
                seed,
                state.probe_count,
            )
            lo_known = await self._binary_search_known(
                db, probe, emit, state, lo=0, hi=seed, phase="downward"
            )
            if lo_known <= 0:
                await db.commit()
                raise RuntimeError(
                    f"bolha scout: no known id below seed {seed} (got {kind})"
                )
            state.lo = lo_known
            state.hi = seed
            log.debug(
                "bolha scout: downward search done lo=%s hi=%s probes=%s",
                state.lo,
                state.hi,
                state.probe_count,
            )
        else:
            state.lo = seed
            log.debug(
                "bolha scout: seed is known (%s); lo=%s probes=%s",
                kind,
                state.lo,
                state.probe_count,
            )

        log.info(
            "bolha scout: phase=gallop enter lo=%s hi=%s probes=%s",
            state.lo,
            state.hi,
            state.probe_count,
        )
        if not await self._gallop_up(db, probe, emit, state):
            await db.commit()
            raise RuntimeError("bolha scout: gallop exceeded safety limits")

        log.info(
            "bolha scout: phase=refine enter lo=%s hi=%s span=%s probes=%s",
            state.lo,
            state.hi,
            state.hi - state.lo,
            state.probe_count,
        )
        await self._refine_up(db, probe, emit, state)
        log.info(
            "bolha scout: phase=refine done lo=%s hi=%s probes=%s",
            state.lo,
            state.hi,
            state.probe_count,
        )

        log.info(
            "bolha scout: phase=binary_search_bracket enter lo=%s hi=%s span=%s probes=%s",
            state.lo,
            state.hi,
            state.hi - state.lo,
            state.probe_count,
        )
        await self._binary_search_known(
            db, probe, emit, state, lo=state.lo, hi=state.hi, phase="bracket"
        )
        log.info(
            "bolha scout: phase=binary_search_bracket done lo=%s hi=%s probes=%s",
            state.lo,
            state.hi,
            state.probe_count,
        )

        new_anchor = state.lo
        log.debug(
            "bolha scout: search complete new_anchor=%s meta_anchor=%s "
            "gap_above_meta=%s will_finalize_advance=%s probes=%s",
            new_anchor,
            meta_anchor,
            new_anchor - meta_anchor,
            new_anchor > meta_anchor,
            state.probe_count,
        )
        if new_anchor > meta_anchor:
            await finalize_scout_last_working_advance(
                db, probe, new_anchor, source_name=self.name, emit=emit
            )
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
        *,
        in_batch: bool = False,
    ) -> ProbeKind | None:
        if state.probe_count >= SCOUT_MAX_PROBES:
            log.debug(
                "bolha scout: probe budget exhausted at ad_id=%s in_batch=%s count=%s",
                ad_id,
                in_batch,
                state.probe_count,
            )
            return None
        state.probe_count += 1
        if not in_batch and state.probe_count > 1:
            await asyncio.sleep(SCOUT_PROBE_DELAY_SECONDS)
        log.debug(
            "bolha scout: single probe ad_id=%s in_batch=%s count=%s lo=%s",
            ad_id,
            in_batch,
            state.probe_count,
            state.lo,
        )
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

    async def _probe_window(
        self,
        db: AsyncSession,
        probe: httpx.AsyncClient,
        emit: EmitFn,
        state: _ScoutState,
        center: int,
    ) -> tuple[int | None, bool]:
        """Probe a LOOKAHEAD_ADS-wide window around *center* in parallel.

        Returns (highest_known_id, budget_exhausted). ``highest_known_id`` is None
        when no active/expired listing exists in the window.
        """
        ad_ids = _window_ad_ids(center)
        n = len(ad_ids)
        probes_before = state.probe_count
        if state.probe_count + n > SCOUT_MAX_PROBES:
            log.debug(
                "bolha scout: window skipped (budget) center=%s ids=%s..%s need=%s have=%s",
                center,
                ad_ids[0] if ad_ids else None,
                ad_ids[-1] if ad_ids else None,
                n,
                probes_before,
            )
            return None, True
        if state.probe_count > 0:
            await asyncio.sleep(SCOUT_PROBE_DELAY_SECONDS)
        state.probe_count += n

        log.debug(
            "bolha scout: window center=%s ids=%s..%s (%s ids) lo=%s probes %s->%s",
            center,
            ad_ids[0] if ad_ids else None,
            ad_ids[-1] if ad_ids else None,
            n,
            state.lo,
            probes_before,
            state.probe_count,
        )

        fetches = await asyncio.gather(
            *[fetch_probe_http(probe, ad_id) for ad_id in ad_ids]
        )
        results: list[tuple[int, ProbeKind | None]] = []
        for fetch in sorted(fetches, key=lambda f: f.ad_id):
            kind = await persist_probe_fetch(
                db,
                fetch,
                source_name=self.name,
                emit=emit,
                last_working_ad_id=state.lo,
                high_water=state.high_water,
            )
            results.append((fetch.ad_id, kind))
        exhausted = any(kind is None for _, kind in results)
        known_ids = [
            ad_id
            for ad_id, kind in results
            if kind is not None and is_known_probe_kind(kind)
        ]
        highest = max(known_ids) if known_ids else None
        log.info(
            "bolha scout: window center=%s outcomes=%s highest_known=%s "
            "exhausted=%s probes=%s",
            center,
            _format_window_outcomes(results),
            highest,
            exhausted,
            state.probe_count,
        )
        if known_ids:
            return highest, exhausted
        return None, exhausted

    async def _gallop_up(
        self,
        db: AsyncSession,
        probe: httpx.AsyncClient,
        emit: EmitFn,
        state: _ScoutState,
    ) -> bool:
        step = SCOUT_GALLOP_STEP
        seed_lo = state.lo
        gallop_iter = 0
        while True:
            gallop_iter += 1
            if state.lo - seed_lo > SCOUT_MAX_ID_SPAN:
                log.error(
                    "bolha scout: exceeded max id span %s above seed %s",
                    SCOUT_MAX_ID_SPAN,
                    seed_lo,
                )
                return False
            candidate = state.lo + step
            log.debug(
                "bolha scout: gallop iter=%s candidate=%s step=%s lo=%s probes=%s",
                gallop_iter,
                candidate,
                step,
                state.lo,
                state.probe_count,
            )
            highest_known, exhausted = await self._probe_window(
                db, probe, emit, state, candidate
            )
            if exhausted:
                log.debug(
                    "bolha scout: gallop stopped (budget) iter=%s candidate=%s probes=%s",
                    gallop_iter,
                    candidate,
                    state.probe_count,
                )
                return False
            if highest_known is not None:
                prev_lo = state.lo
                state.lo = highest_known
                step = min(step * 2, SCOUT_MAX_ID_SPAN)
                log.debug(
                    "bolha scout: gallop found known id=%s lo %s->%s step=%s probes=%s",
                    highest_known,
                    prev_lo,
                    state.lo,
                    step,
                    state.probe_count,
                )
                continue
            state.hi = candidate + SCOUT_PROBE_WINDOW_RADIUS
            log.debug(
                "bolha scout: gallop bracket found lo=%s hi=%s candidate=%s "
                "iters=%s probes=%s",
                state.lo,
                state.hi,
                candidate,
                gallop_iter,
                state.probe_count,
            )
            log.info(
                "bolha scout: gallop bracket [%s, %s] "
                "(no known in window around %s)",
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
        refine_iter = 0
        while state.hi - state.lo > SCOUT_REFINE_STEP:
            refine_iter += 1
            candidate = state.lo + SCOUT_REFINE_STEP
            log.debug(
                "bolha scout: refine iter=%s candidate=%s lo=%s hi=%s span=%s probes=%s",
                refine_iter,
                candidate,
                state.lo,
                state.hi,
                state.hi - state.lo,
                state.probe_count,
            )
            highest_known, exhausted = await self._probe_window(
                db, probe, emit, state, candidate
            )
            if exhausted:
                log.debug(
                    "bolha scout: refine stopped (budget) iter=%s probes=%s",
                    refine_iter,
                    state.probe_count,
                )
                return
            if highest_known is not None:
                prev_lo = state.lo
                state.lo = highest_known
                log.debug(
                    "bolha scout: refine found known id=%s lo %s->%s probes=%s",
                    highest_known,
                    prev_lo,
                    state.lo,
                    state.probe_count,
                )
            else:
                state.hi = candidate + SCOUT_PROBE_WINDOW_RADIUS
                log.debug(
                    "bolha scout: refine narrowed hi=%s candidate=%s probes=%s",
                    state.hi,
                    candidate,
                    state.probe_count,
                )
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
        phase: str = "binary",
    ) -> int:
        """Return highest known id in (lo, hi]; updates state.lo."""
        log.debug(
            "bolha scout: %s enter lo=%s hi=%s span=%s probes=%s",
            phase,
            lo,
            hi,
            hi - lo,
            state.probe_count,
        )
        step = 0
        while hi - lo > 1:
            step += 1
            mid = (lo + hi) // 2
            lo_before, hi_before = lo, hi
            highest_known, exhausted = await self._probe_window(
                db, probe, emit, state, mid
            )
            if exhausted:
                log.debug(
                    "bolha scout: %s stopped (budget) step=%s mid=%s lo=%s hi=%s probes=%s",
                    phase,
                    step,
                    mid,
                    lo,
                    hi,
                    state.probe_count,
                )
                break
            if highest_known is not None:
                lo = max(lo, highest_known)
                # Window found known ids but lo did not advance (already at the
                # frontier). Without shrinking hi, mid stays fixed forever.
                if lo == lo_before:
                    hi = min(hi, mid - 1)
            else:
                hi = max(lo + 1, mid - SCOUT_PROBE_WINDOW_RADIUS - 1)
            log.debug(
                "bolha scout: %s step=%s mid=%s lo %s->%s hi %s->%s highest=%s probes=%s",
                phase,
                step,
                mid,
                lo_before,
                lo,
                hi_before,
                hi,
                highest_known,
                state.probe_count,
            )
        state.lo = lo
        state.hi = hi
        log.debug(
            "bolha scout: %s done steps=%s result_lo=%s state.lo=%s state.hi=%s probes=%s",
            phase,
            step,
            lo,
            state.lo,
            state.hi,
            state.probe_count,
        )
        return lo
