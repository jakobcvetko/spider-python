from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.listings import listing_default_order
from app.avtonet_ads_serialize import avtonet_ad_to_out as _avtonet_ad_to_out
from app.bolha_ads_serialize import bolha_ad_to_out as _bolha_ad_to_out
from app.listing_times import listing_times_by_external_ids
from app.config import get_settings
from app.database import get_db
from app.deps import get_admin_user_from_cookie, require_admin
from app.models import (
    AvtonetAd,
    AvtonetScrapeMeta,
    BolhaAd,
    Listing,
    User,
)
from app.models.avtonet_ad import AD_STATUS_SUCCESS as AVTONET_AD_STATUS_SUCCESS
from app.models.bolha_ad import AD_STATUS_SUCCESS
from app.schemas.admin import (
    AdminListingOut,
    AdminUserOut,
    AvtonetAdMatchResponse,
    AvtonetAdOut,
    AvtonetScrapeState,
    BolhaAdMatchResponse,
    BolhaAdOut,
    RunSourceBody,
    RunSourceResponse,
    ScraperStatus,
    TriggerResponse,
)
from app.scraper_events import get_event_bus, make_event
from app.telegram.notify import notify_new_matches
from matcher.match import AVTONET_SOURCE, BOLHA_SOURCE, match_listing

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
    source: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
) -> list[Listing]:
    stmt = select(Listing).order_by(*listing_default_order()).limit(limit)
    if source is not None:
        stmt = stmt.where(Listing.source == source)
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

    known = {s.name for s in ALL_SOURCES} | {"bolha.com", "avto.net"}
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


def _ads_with_listing_times(
    rows: list[BolhaAd] | list[AvtonetAd],
    *,
    times_by_external_id: dict[str, tuple[datetime, datetime | None]],
    to_out,
) -> list:
    out: list = []
    for row in rows:
        listing_created_at: datetime | None = None
        listing_published_at: datetime | None = None
        if row.status == AD_STATUS_SUCCESS:
            times = times_by_external_id.get(str(row.ad_id))
            if times is not None:
                listing_created_at, listing_published_at = times
        out.append(
            to_out(
                row,
                listing_created_at=listing_created_at,
                listing_published_at=listing_published_at,
            )
        )
    return out


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
    success_ids = [str(r.ad_id) for r in rows if r.status == AD_STATUS_SUCCESS]
    times = await listing_times_by_external_ids(db, BOLHA_SOURCE, success_ids)
    return _ads_with_listing_times(rows, times_by_external_id=times, to_out=_bolha_ad_to_out)


@router.post("/bolha/ads/{ad_id}/match", response_model=BolhaAdMatchResponse)
async def run_matcher_for_bolha_ad(
    ad_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> BolhaAdMatchResponse:
    ad_row = await db.get(BolhaAd, ad_id)
    if ad_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ad not found")
    if ad_row.status != AD_STATUS_SUCCESS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Matcher only applies to ads with status success",
        )

    listing_id = (
        await db.execute(
            select(Listing.id).where(
                Listing.source == BOLHA_SOURCE,
                Listing.external_id == str(ad_id),
            )
        )
    ).scalar_one_or_none()
    if listing_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No listing row for this ad (run lookahead/backfill first)",
        )

    new_matches = await match_listing(db, listing_id)
    await db.commit()

    if new_matches:
        await notify_new_matches(new_matches)

    return BolhaAdMatchResponse(
        ad_id=ad_id,
        listing_id=listing_id,
        matches_created=len(new_matches),
    )


@router.get("/avtonet/state", response_model=AvtonetScrapeState)
async def avtonet_scrape_state(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> AvtonetScrapeState:
    cfg = get_settings()
    meta = await db.get(AvtonetScrapeMeta, 1)
    last_working = int(meta.last_working_ad_id or 0) if meta else 0
    return AvtonetScrapeState(
        last_working_ad_id=last_working,
        last_working_at=meta.last_working_at if meta else None,
        last_batch_started_at=meta.last_batch_started_at if meta else None,
        lookahead_batch_size=cfg.avtonet_lookahead_batch_size,
        probe_delay_seconds=cfg.avtonet_probe_delay_seconds,
        fetch_mode=cfg.resolved_avtonet_fetch_mode,
        scraperapi_enabled=cfg.resolved_avtonet_fetch_mode == "scraperapi",
    )


@router.get("/avtonet/ads", response_model=list[AvtonetAdOut])
async def avtonet_ads(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
    limit: int = Query(default=500, ge=1, le=10_000),
    offset: int = Query(default=0, ge=0),
) -> list[AvtonetAdOut]:
    stmt = (
        select(AvtonetAd)
        .order_by(AvtonetAd.ad_id.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    success_ids = [str(r.ad_id) for r in rows if r.status == AVTONET_AD_STATUS_SUCCESS]
    times = await listing_times_by_external_ids(db, AVTONET_SOURCE, success_ids)
    return _ads_with_listing_times(rows, times_by_external_id=times, to_out=_avtonet_ad_to_out)


@router.post("/avtonet/ads/{ad_id}/match", response_model=AvtonetAdMatchResponse)
async def run_matcher_for_avtonet_ad(
    ad_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> AvtonetAdMatchResponse:
    ad_row = await db.get(AvtonetAd, ad_id)
    if ad_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ad not found")
    if ad_row.status != AVTONET_AD_STATUS_SUCCESS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Matcher only applies to ads with status success",
        )

    listing_id = (
        await db.execute(
            select(Listing.id).where(
                Listing.source == AVTONET_SOURCE,
                Listing.external_id == str(ad_id),
            )
        )
    ).scalar_one_or_none()
    if listing_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No listing row for this ad (run lookahead first)",
        )

    new_matches = await match_listing(db, listing_id)
    await db.commit()

    if new_matches:
        await notify_new_matches(new_matches)

    return AvtonetAdMatchResponse(
        ad_id=ad_id,
        listing_id=listing_id,
        matches_created=len(new_matches),
    )


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
