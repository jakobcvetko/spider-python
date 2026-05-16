from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.listings import listing_default_order
from app.bolha_ads_serialize import bolha_ad_to_out as _bolha_ad_to_out
from app.config import get_settings
from app.database import get_db
from app.deps import get_admin_user_from_cookie, require_admin
from app.models import (
    BolhaAd,
    BolhaAdProbe,
    BolhaAdState,
    BolhaInactiveAd,
    BolhaScrapeMeta,
    Listing,
    User,
)
from app.schemas.admin import (
    AdminListingOut,
    AdminUserOut,
    BolhaAdOut,
    BolhaAdStateOut,
    BolhaProgressiveRow,
    BolhaProgressiveState,
    RunSourceBody,
    RunSourceResponse,
    ScraperStatus,
    TriggerResponse,
)
from app.scraper_events import get_event_bus, make_event

router = APIRouter(prefix="/admin", tags=["admin"])
settings = get_settings()
log = logging.getLogger(__name__)

# How long after the last heartbeat we still consider the worker "connected".
HEARTBEAT_GRACE_SECONDS = 15.0


def _scraper_source_names() -> list[str]:
    # Imported lazily to avoid pulling scraper deps into the API process at import time.
    from scraper.sources import ALL_SOURCES

    return [s.name for s in ALL_SOURCES]


def _build_status(recent_events_limit: int = 50) -> ScraperStatus:
    bus = get_event_bus()
    last = bus.last_heartbeat_ts()
    now = time.time()
    age = (now - last) if last is not None else None
    connected = age is not None and age <= HEARTBEAT_GRACE_SECONDS
    snapshot = bus.snapshot()
    return ScraperStatus(
        connected=connected,
        last_heartbeat_ts=last,
        seconds_since_heartbeat=age,
        sources=_scraper_source_names(),
        interval_seconds=settings.scrape_interval_seconds,
        recent_events=snapshot[-recent_events_limit:],
    )


@router.get("/listings", response_model=list[AdminListingOut])
async def admin_list_listings(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
    limit: int = Query(default=100, ge=1, le=100),
) -> list[Listing]:
    stmt = select(Listing).order_by(*listing_default_order()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[User]:
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return list(result.scalars().all())


@router.get("/scraper/status", response_model=ScraperStatus)
async def scraper_status(_: User = Depends(require_admin)) -> ScraperStatus:
    return _build_status()


@router.post("/scraper/trigger", response_model=TriggerResponse)
async def trigger_scraper(current: User = Depends(require_admin)) -> TriggerResponse:
    bus = get_event_bus()
    reason = f"manual trigger by {current.email}"
    await bus.send_command({"action": "run_now", "reason": reason})
    return TriggerResponse(queued=True, reason=reason)


@router.post("/scraper/run-source", response_model=RunSourceResponse)
async def run_source_scrape(
    body: RunSourceBody,
    current: User = Depends(require_admin),
) -> RunSourceResponse:
    from scraper.sources import ALL_SOURCES

    known = {s.name for s in ALL_SOURCES} | {"bolha.com"}
    if body.source not in known:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown source {body.source!r}. Known: {sorted(known)}",
        )
    bus = get_event_bus()
    reason = f"admin debug scrape by {current.email}"
    await bus.send_command(
        {"action": "run_source", "source": body.source, "reason": reason}
    )
    return RunSourceResponse(queued=True, reason=reason, source=body.source)


@router.get("/bolha/progressive-state", response_model=BolhaProgressiveState)
async def bolha_progressive_state(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> BolhaProgressiveState:
    from scraper.sources.bolha_common import LOOKAHEAD_ADS

    now = datetime.now(timezone.utc)
    meta = await db.get(BolhaScrapeMeta, 1)
    if meta is None:
        hp_max = 0
        high_water = 0
        lw = 0
        last_working_at = None
        last_fetch_started_at = None
    else:
        hp_max = int(meta.last_homepage_max or 0)
        high_water = int(meta.last_fetch_high_water or 0)
        lw = int(meta.last_working_ad_id or 0)
        last_working_at = meta.last_working_at
        last_fetch_started_at = meta.last_fetch_started_at

    r = await db.execute(
        text(
            """
            SELECT MAX(CAST(external_id AS BIGINT))
            FROM listings
            WHERE source = 'bolha.com' AND external_id ~ '^[0-9]+$'
            """
        )
    )
    db_max_raw = r.scalar_one_or_none()
    db_max = int(db_max_raw) if db_max_raw is not None else 0

    scan_anchor = max(hp_max, high_water, db_max)
    pivot_id = lw if lw > 0 else scan_anchor

    la_ids = list(range(pivot_id + 1, pivot_id + LOOKAHEAD_ADS + 1))
    tail_ids = list(range(pivot_id + 1, pivot_id + 101))
    all_ids = sorted(set([pivot_id] + la_ids + tail_ids))

    probes = (
        (
            await db.execute(select(BolhaAdProbe).where(BolhaAdProbe.ad_id.in_(all_ids)))
        )
        .scalars()
        .all()
    )
    probe_by_id = {p.ad_id: p for p in probes}

    in_rows = (
        (
            await db.execute(
                select(BolhaInactiveAd).where(BolhaInactiveAd.ad_id.in_(all_ids))
            )
        )
        .scalars()
        .all()
    )
    inactive_by_id = {r.ad_id: r for r in in_rows}

    st_rows = (
        (await db.execute(select(BolhaAdState).where(BolhaAdState.ad_id.in_(all_ids))))
        .scalars()
        .all()
    )
    state_by_id = {r.ad_id: r for r in st_rows}

    def build_row(
        ad_id: int,
        *,
        zone: str,
    ) -> BolhaProgressiveRow:
        pr = probe_by_id.get(ad_id)
        inc = inactive_by_id.get(ad_id)
        st = state_by_id.get(ad_id)
        pipeline = st.status if st else None

        if pr is None:
            disp = "no_info"
            if st is not None:
                if st.status == "timed_out":
                    disp = "timed_out"
                elif st.status == "expired":
                    disp = "expired"
                elif st.status in ("pending_fallback", "fallback_warming"):
                    disp = "in_progress"
                elif st.status == "lookahead":
                    disp = "inactive"
            return BolhaProgressiveRow(
                ad_id=ad_id,
                zone=zone,
                display_status=disp,
                outcome=None,
                http_status=None,
                gtm_ad_status=None,
                fetched_at=None,
                inactive_age_seconds=None,
                detail=None,
                pipeline_status=pipeline,
            )
        oc = pr.outcome
        age_s: float | None = None
        if (
            st is not None
            and st.first_fallback_scrape_at is not None
            and st.status in ("pending_fallback", "fallback_warming")
        ):
            age_s = (now - st.first_fallback_scrape_at).total_seconds()
        elif inc is not None:
            age_s = (now - inc.first_inactive_at).total_seconds()

        if st is not None and st.status == "timed_out":
            disp = "timed_out"
        elif st is not None and st.status == "expired":
            disp = "expired"
        elif st is not None and st.status in ("pending_fallback", "fallback_warming"):
            disp = "successful" if oc == "active" else "in_progress"
        elif oc == "active":
            disp = "successful"
        elif oc == "expired":
            disp = "expired"
        elif oc == "not_yet_created":
            disp = "not_yet_created"
        elif oc == "past_warming":
            disp = "in_progress"
        elif oc == "past_timed_out":
            disp = "timed_out"
        elif oc in ("http_error", "bad_http_status"):
            disp = "error"
        elif oc == "inactive_non_active":
            disp = "inactive"
        else:
            disp = "inactive"

        return BolhaProgressiveRow(
            ad_id=ad_id,
            zone=zone,
            display_status=disp,
            outcome=oc,
            http_status=pr.http_status,
            gtm_ad_status=pr.gtm_ad_status,
            fetched_at=pr.fetched_at,
            inactive_age_seconds=round(age_s, 1) if age_s is not None else None,
            detail=pr.detail,
            pipeline_status=pipeline,
        )

    lookahead_rows = [
        build_row(i, zone="lookahead") for i in la_ids
    ]
    pivot_row = build_row(pivot_id, zone="last_working" if lw > 0 else "anchor")
    tail_rows = [build_row(i, zone="tail") for i in tail_ids]

    return BolhaProgressiveState(
        look_ahead_count=LOOKAHEAD_ADS,
        last_working_ad_id=lw,
        last_working_at=last_working_at,
        scan_anchor_ad_id=scan_anchor,
        last_homepage_max=hp_max,
        last_fetch_high_water=high_water,
        last_fetch_started_at=last_fetch_started_at,
        db_numeric_max=db_max,
        lookahead_rows=lookahead_rows,
        pivot_row=pivot_row,
        tail_rows=tail_rows,
    )


@router.get("/bolha/ads", response_model=list[BolhaAdOut])
async def bolha_ads(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
    limit: int = Query(default=500, ge=1, le=10_000),
    offset: int = Query(default=0, ge=0),
) -> list[BolhaAdOut]:
    stmt = (
        select(BolhaAd)
        .order_by(BolhaAd.ad_id.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_bolha_ad_to_out(r) for r in rows]


@router.get("/bolha/ad-states", response_model=list[BolhaAdStateOut])
async def bolha_ad_states(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
    limit: int = Query(default=10_000, ge=1, le=50_000),
) -> list[BolhaAdState]:
    stmt = select(BolhaAdState).order_by(BolhaAdState.ad_id.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.websocket("/scraper/ws")
async def scraper_ws(websocket: WebSocket) -> None:
    cookie_token = websocket.cookies.get(settings.session_cookie_name)
    user = await get_admin_user_from_cookie(cookie_token)
    if user is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    bus = get_event_bus()

    try:
        snapshot = bus.snapshot()
        await websocket.send_text(
            json.dumps(
                {
                    "kind": "snapshot",
                    "events": snapshot,
                    "status": _build_status(recent_events_limit=0).model_dump(),
                }
            )
        )

        async with bus.subscribe() as queue:
            while True:
                # Forward events; also send periodic status pings so the UI can
                # update the "scraper connected" badge even when there's no event.
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=2.0)
                    await websocket.send_text(
                        json.dumps({"kind": "event", "event": event})
                    )
                except asyncio.TimeoutError:
                    await websocket.send_text(
                        json.dumps(
                            {
                                "kind": "status",
                                "status": _build_status(recent_events_limit=0).model_dump(),
                            }
                        )
                    )
    except WebSocketDisconnect:
        return
    except Exception:  # noqa: BLE001
        log.exception("admin ws error")
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except Exception:  # noqa: BLE001
            pass


# Re-export so callers know we used `make_event` (keeps imports tidy in tests).
__all__ = ["router", "make_event"]
