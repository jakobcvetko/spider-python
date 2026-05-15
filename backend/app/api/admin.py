from __future__ import annotations

import asyncio
import json
import logging
import time

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.deps import get_admin_user_from_cookie, require_admin
from app.models import User
from app.schemas.admin import AdminUserOut, ScraperStatus, TriggerResponse
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
