from __future__ import annotations

import asyncio
import logging

from app.database import SessionLocal
from app.telegram.client import get_telegram_client
from app.telegram.webhook import handle_update

log = logging.getLogger(__name__)


async def run_polling(stop: asyncio.Event) -> None:
    client = get_telegram_client()
    if client is None:
        return

    offset: int | None = None
    log.info("telegram: long polling started")

    while not stop.is_set():
        try:
            updates = await client.get_updates(offset=offset, timeout=30)
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

    log.info("telegram: long polling stopped")
