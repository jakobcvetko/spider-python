"""Standalone matcher worker.

Listens on Postgres ``matcher_jobs`` NOTIFY (enqueued by bolha lookahead after each
listing upsert) and creates ``scraper_matches`` rows without blocking scrapers.

Run with:  uv run python -m matcher.worker
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import sys
import uuid

import asyncpg

from app.database import SessionLocal
from app.matcher_jobs import MATCHER_JOBS_CHANNEL
from app.scraper_events import _asyncpg_dsn
from matcher.match import match_listing

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("matcher")


async def _process_listing(listing_id: uuid.UUID) -> None:
    async with SessionLocal() as db:
        try:
            await match_listing(db, listing_id)
            await db.commit()
        except Exception:
            await db.rollback()
            log.exception("matcher: failed for listing %s", listing_id)


def _make_notify_handler(stop: asyncio.Event):
    def on_notify(
        _conn: asyncpg.Connection,
        _pid: int,
        _channel: str,
        payload: str,
    ) -> None:
        if stop.is_set():
            return
        try:
            data = json.loads(payload)
            listing_id = uuid.UUID(data["listing_id"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            log.warning("matcher: dropping malformed job payload: %r", payload[:200])
            return
        asyncio.create_task(_process_listing(listing_id))

    return on_notify


async def _run() -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    handler = _make_notify_handler(stop)
    conn = await asyncpg.connect(dsn=_asyncpg_dsn())
    try:
        await conn.add_listener(MATCHER_JOBS_CHANNEL, handler)
        log.info("matcher worker listening on channel %s", MATCHER_JOBS_CHANNEL)
        await stop.wait()
    finally:
        await conn.remove_listener(MATCHER_JOBS_CHANNEL, handler)
        await conn.close()
    log.info("matcher worker stopped")


def main() -> None:
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
