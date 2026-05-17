from __future__ import annotations

import asyncio
import logging

import httpx

from app.database import SessionLocal
from app.telegram.client import get_telegram_client
from app.telegram.poll_lock import release_polling_lock, try_acquire_polling_lock
from app.telegram.webhook import handle_update

log = logging.getLogger(__name__)

_CONFLICT_BACKOFF_SECONDS = 5


async def run_polling(stop: asyncio.Event) -> None:
    client = get_telegram_client()
    if client is None:
        return

    if not try_acquire_polling_lock():
        log.warning(
            "telegram: another process is already polling getUpdates "
            "(stop extra uvicorn instances or set TELEGRAM_POLLING=false)"
        )
        return

    offset: int | None = None
    log.info("telegram: long polling started")

    try:
        while not stop.is_set():
            try:
                updates = await client.get_updates(offset=offset, timeout=30)
            except httpx.ReadTimeout:
                continue
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 409:
                    log.warning(
                        "telegram: getUpdates conflict (another poller active); "
                        "retrying in %ss",
                        _CONFLICT_BACKOFF_SECONDS,
                    )
                    await asyncio.sleep(_CONFLICT_BACKOFF_SECONDS)
                    continue
                log.exception("telegram: getUpdates failed")
                await asyncio.sleep(3)
                continue
            except Exception:
                log.exception("telegram: getUpdates failed")
                await asyncio.sleep(3)
                continue

            for update in updates:
                update_id = update.get("update_id")
                if isinstance(update_id, int):
                    offset = update_id + 1

                async with SessionLocal() as db:
                    try:
                        await handle_update(db, update)
                    except Exception:
                        await db.rollback()
                        log.exception("telegram: failed to handle update %s", update_id)

            if not updates:
                await asyncio.sleep(0.1)
    finally:
        release_polling_lock()
        log.info("telegram: long polling stopped")
