"""Standalone scraper worker.

Runs APScheduler jobs that periodically fetch new listings from each source
and upsert them into Postgres (deduped by source + external_id).

Run with:    uv run python -m scraper.worker
"""

from __future__ import annotations

import asyncio
import logging
import random
import signal

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings
from app.database import SessionLocal
from scraper.base import Source, upsert_items
from scraper.sources import ALL_SOURCES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("scraper")


async def run_source(source: Source, client: httpx.AsyncClient) -> None:
    log.info("[%s] starting fetch", source.name)
    try:
        items = await source.fetch(client)
    except Exception:
        log.exception("[%s] fetch raised", source.name)
        return

    log.info("[%s] parsed %d candidate items", source.name, len(items))

    if not items:
        return

    async with SessionLocal() as db:
        try:
            inserted = await upsert_items(db, source.name, items)
        except Exception:
            log.exception("[%s] upsert failed", source.name)
            return

    log.info("[%s] inserted %d new listings (skipped %d duplicates)",
             source.name, inserted, len(items) - inserted)


async def main() -> None:
    settings = get_settings()
    interval = settings.scrape_interval_seconds

    log.info("starting scraper worker, interval=%ss, sources=%s",
             interval, [s.name for s in ALL_SOURCES])

    headers = {
        "User-Agent": settings.scraper_user_agent,
        "Accept-Language": "sl,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml",
    }
    client = httpx.AsyncClient(
        headers=headers,
        follow_redirects=True,
        timeout=httpx.Timeout(30.0),
    )

    scheduler = AsyncIOScheduler()

    for source in ALL_SOURCES:
        # add small per-source jitter so we don't hit both at the same instant
        jitter = random.randint(0, max(1, interval // 4))
        trigger = IntervalTrigger(seconds=interval, jitter=jitter)
        scheduler.add_job(
            run_source,
            trigger=trigger,
            args=[source, client],
            id=f"scrape-{source.name}",
            max_instances=1,
            coalesce=True,
            next_run_time=None,  # let scheduler schedule first run after `interval`
            misfire_grace_time=interval,
        )

    scheduler.start()

    # kick off an immediate first run for each source
    for source in ALL_SOURCES:
        asyncio.create_task(run_source(source, client))

    stop_event = asyncio.Event()

    def _stop(*_: object) -> None:
        log.info("stop signal received, shutting down")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            pass

    await stop_event.wait()
    scheduler.shutdown(wait=False)
    await client.aclose()
    log.info("scraper worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
