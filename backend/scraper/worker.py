"""Standalone scraper worker.

Runs APScheduler jobs that periodically fetch new listings from each source
and upsert them into Postgres (deduped by source + external_id).

Also publishes realtime events (and listens for run-now commands) on Postgres
``NOTIFY`` channels — see ``app.scraper_events`` — so the admin UI can show
live scraper activity.

Run with:    uv run python -m scraper.worker
            uv run python -m scraper.worker --sources bolha.lookahead
"""

from __future__ import annotations

from argparse import ArgumentParser
import asyncio
import json
import logging
import random
import signal
import sys
import time

import asyncpg
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings
from app.database import SessionLocal
from app.scraper_events import (
    COMMANDS_CHANNEL,
    asyncpg_connection,
    make_event,
    publish_event,
)
from scraper.base import Source, item_to_dict, upsert_items
from scraper.sources import ALL_SOURCES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("scraper")

HEARTBEAT_INTERVAL_SECONDS = 5

BOLHA_EMIT_SOURCES = frozenset({"bolha.lookahead", "bolha.backfill", "bolha.scout"})

_NO_INTERVAL_SOURCES = frozenset({"bolha.lookahead", "bolha.scout"})


def _listing_source_for(source: Source) -> str:
    return getattr(source, "listing_source", None) or source.name


def worker_sources_from_argv(argv: list[str] | None = None) -> list[Source]:
    """Parse ``--sources`` (comma-separated). Empty / omitted means all ``ALL_SOURCES``."""
    parser = ArgumentParser(
        prog="python -m scraper.worker",
        description="Spider scraper worker.",
    )
    parser.add_argument(
        "--sources",
        metavar="NAMES",
        default="",
        help=(
            "Comma-separated source names, e.g. bolha.lookahead,bolha.scout. "
            "Default: run every registered source."
        ),
    )
    args = parser.parse_args(argv)
    raw = (args.sources or "").strip()
    if not raw:
        return list(ALL_SOURCES)
    wanted = {p.strip() for p in raw.split(",") if p.strip()}
    by_name = {s.name: s for s in ALL_SOURCES}
    unknown = sorted(wanted - by_name.keys())
    if unknown:
        parser.error(
            "unknown source(s): "
            + ", ".join(unknown)
            + "; known: "
            + ", ".join(sorted(by_name))
        )
    return [s for s in ALL_SOURCES if s.name in wanted]


class EventPublisher:
    """Single asyncpg connection used to NOTIFY events. Calls are serialised."""

    def __init__(self) -> None:
        self._conn: asyncpg.Connection | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        from app.scraper_events import _asyncpg_dsn  # local to avoid cycles
        self._conn = await asyncpg.connect(dsn=_asyncpg_dsn())

    async def stop(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def emit(self, event: dict) -> None:
        if self._conn is None:
            return
        async with self._lock:
            try:
                await publish_event(self._conn, event)
            except Exception:
                log.exception("failed to publish scraper event")


def _make_http_event_hooks(publisher: EventPublisher, source_holder: dict[str, str | None]):
    """Return httpx event hooks that emit request/response events.

    ``source_holder`` lets ``run_source`` set the current source name before
    fetching so the events include it.
    """
    async def on_request(request: httpx.Request) -> None:
        request.extensions["spider_t0"] = time.perf_counter()
        await publisher.emit(
            make_event(
                "http_request",
                source=source_holder.get("name"),
                message=f"{request.method} {request.url}",
                data={
                    "method": request.method,
                    "url": str(request.url),
                },
            )
        )

    async def on_response(response: httpx.Response) -> None:
        t0 = response.request.extensions.get("spider_t0")
        elapsed_ms = round((time.perf_counter() - t0) * 1000) if t0 else None
        await publisher.emit(
            make_event(
                "http_response",
                source=source_holder.get("name"),
                message=f"{response.status_code} {response.request.method} {response.request.url}",
                data={
                    "status": response.status_code,
                    "method": response.request.method,
                    "url": str(response.request.url),
                    "elapsed_ms": elapsed_ms,
                    "bytes": int(response.headers.get("content-length") or 0) or None,
                },
            )
        )

    return {"request": [on_request], "response": [on_response]}


async def run_source(
    source: Source,
    client: httpx.AsyncClient,
    publisher: EventPublisher,
    source_holder: dict[str, str | None],
    *,
    debug: bool = False,
) -> None:
    source_holder["name"] = source.name
    log.info("[%s] starting fetch", source.name)
    await publisher.emit(make_event("fetch_start", source=source.name, message="fetch starting"))

    listing_src = _listing_source_for(source)
    try:
        if source.name in BOLHA_EMIT_SOURCES:
            items = await source.fetch(client, emit=publisher.emit)  # type: ignore[call-arg]
        else:
            items = await source.fetch(client)
    except Exception as e:  # noqa: BLE001
        log.exception("[%s] fetch raised", source.name)
        await publisher.emit(
            make_event(
                "fetch_error",
                source=source.name,
                message=f"{type(e).__name__}: {e}",
            )
        )
        return

    log.info("[%s] parsed %d candidate items", source.name, len(items))
    await publisher.emit(
        make_event(
            "parsed",
            source=source.name,
            message=f"parsed {len(items)} candidate items",
            data={"count": len(items)},
        )
    )

    if debug and not items:
        await publisher.emit(
            make_event(
                "parsed_empty",
                source=source.name,
                message="0 candidate listings — scroll up for HTTP status/redirects; HTML may be a bot wall or selectors may not match the page",
                data={"hint": "empty_parse"},
            )
        )

    if debug and items:
        preview: list[dict] = []
        for item in items[:15]:
            row = item_to_dict(item)
            row.pop("raw", None)
            title = row.get("title")
            if isinstance(title, str) and len(title) > 120:
                row["title"] = title[:117] + "..."
            preview.append(row)
        await publisher.emit(
            make_event(
                "parsed_preview",
                source=source.name,
                message=f"preview {len(preview)} of {len(items)} parsed rows (admin debug)",
                data={"total": len(items), "shown": len(preview), "items": preview},
            )
        )

    if not items:
        return

    async with SessionLocal() as db:
        try:
            inserted = await upsert_items(db, listing_src, items)
        except Exception as e:  # noqa: BLE001
            log.exception("[%s] upsert failed", source.name)
            await publisher.emit(
                make_event(
                    "upsert_error",
                    source=source.name,
                    message=f"{type(e).__name__}: {e}",
                )
            )
            return

    skipped = len(items) - inserted
    log.info("[%s] inserted %d new listings (skipped %d duplicates)",
             source.name, inserted, skipped)
    await publisher.emit(
        make_event(
            "upsert",
            source=source.name,
            message=f"inserted {inserted} new, skipped {skipped} duplicates",
            data={"inserted": inserted, "skipped": skipped},
        )
    )


async def run_all_sources(
    sources: list[Source],
    client: httpx.AsyncClient,
    publisher: EventPublisher,
    source_holder: dict[str, str | None],
    *,
    reason: str,
) -> None:
    await publisher.emit(
        make_event("cycle_start", message=f"running all sources ({reason})", data={"reason": reason})
    )
    for source in sources:
        await run_source(source, client, publisher, source_holder)
    await publisher.emit(make_event("cycle_done", message="cycle complete"))


async def heartbeat_loop(publisher: EventPublisher, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        await publisher.emit(
            make_event("heartbeat", message="alive", data={"interval_s": HEARTBEAT_INTERVAL_SECONDS})
        )
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=HEARTBEAT_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            continue


async def commands_loop(
    sources: list[Source],
    client: httpx.AsyncClient,
    publisher: EventPublisher,
    source_holder: dict[str, str | None],
    stop_event: asyncio.Event,
) -> None:
    """LISTEN on the commands channel and run sources on demand."""
    in_flight = False

    async def handle_run_now(reason: str) -> None:
        nonlocal in_flight
        if in_flight:
            await publisher.emit(
                make_event(
                    "trigger_skipped",
                    message="run already in progress; ignoring trigger",
                )
            )
            return
        in_flight = True
        try:
            await run_all_sources(sources, client, publisher, source_holder, reason=reason)
        finally:
            in_flight = False

    async def handle_run_source(source_name: str, reason: str) -> None:
        nonlocal in_flight
        if in_flight:
            await publisher.emit(
                make_event(
                    "trigger_skipped",
                    message="run already in progress; ignoring single-source scrape",
                    data={"requested_source": source_name},
                )
            )
            return
        if source_name == "bolha.com":
            matches = [
                s
                for s in sources
                if getattr(s, "listing_source", None) == "bolha.com"
            ]
            if not matches:
                known = [s.name for s in sources]
                await publisher.emit(
                    make_event(
                        "debug_source_unknown",
                        message=f"unknown source {source_name!r}; known: {known}",
                        data={"source": source_name, "known": known},
                    )
                )
                return
            in_flight = True
            t0 = time.perf_counter()
            try:
                for match in matches:
                    await publisher.emit(
                        make_event(
                            "debug_source_start",
                            source=match.name,
                            message=f"admin bolha pipeline step ({reason})",
                            data={"reason": reason, "pipeline": "bolha.com"},
                        )
                    )
                    await run_source(match, client, publisher, source_holder, debug=True)
                    elapsed_ms = round((time.perf_counter() - t0) * 1000)
                    await publisher.emit(
                        make_event(
                            "debug_source_done",
                            source=match.name,
                            message=f"bolha pipeline step finished in {elapsed_ms}ms",
                            data={"elapsed_ms": elapsed_ms},
                        )
                    )
            finally:
                in_flight = False
            return

        match = next((s for s in sources if s.name == source_name), None)
        if match is None:
            known = [s.name for s in sources]
            await publisher.emit(
                make_event(
                    "debug_source_unknown",
                    message=f"unknown source {source_name!r}; known: {known}",
                    data={"source": source_name, "known": known},
                )
            )
            return
        in_flight = True
        t0 = time.perf_counter()
        try:
            await publisher.emit(
                make_event(
                    "debug_source_start",
                    source=match.name,
                    message=f"admin single-source scrape ({reason})",
                    data={"reason": reason},
                )
            )
            await run_source(match, client, publisher, source_holder, debug=True)
        finally:
            elapsed_ms = round((time.perf_counter() - t0) * 1000)
            await publisher.emit(
                make_event(
                    "debug_source_done",
                    source=match.name,
                    message=f"single-source scrape finished in {elapsed_ms}ms",
                    data={"elapsed_ms": elapsed_ms},
                )
            )
            in_flight = False

    while not stop_event.is_set():
        try:
            async with asyncpg_connection() as conn:
                queue: asyncio.Queue[str] = asyncio.Queue()

                def _on_command(_c, _pid, _channel, payload: str) -> None:
                    queue.put_nowait(payload)

                await conn.add_listener(COMMANDS_CHANNEL, _on_command)
                log.info("listening on %s for run-now commands", COMMANDS_CHANNEL)

                while not stop_event.is_set():
                    get_task = asyncio.create_task(queue.get())
                    stop_task = asyncio.create_task(stop_event.wait())
                    done, pending = await asyncio.wait(
                        {get_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
                    )
                    for p in pending:
                        p.cancel()
                    if stop_task in done:
                        break

                    payload = get_task.result()
                    try:
                        command = json.loads(payload)
                    except json.JSONDecodeError:
                        log.warning("ignoring malformed command payload: %r", payload[:200])
                        continue

                    action = command.get("action")
                    if action == "run_now":
                        reason = command.get("reason") or "manual trigger"
                        asyncio.create_task(handle_run_now(reason))
                    elif action == "run_source":
                        source_name = command.get("source")
                        if not isinstance(source_name, str) or not source_name.strip():
                            log.warning("run_source command missing source: %r", command)
                            continue
                        reason = command.get("reason") or "admin single-source scrape"
                        asyncio.create_task(handle_run_source(source_name.strip(), str(reason)))
                    else:
                        log.info("unknown command action: %r", action)

                await conn.remove_listener(COMMANDS_CHANNEL, _on_command)
        except (asyncpg.PostgresError, OSError):
            log.exception("commands listener crashed; reconnecting in 2s")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                continue


async def main(sources: list[Source]) -> None:
    settings = get_settings()
    interval = settings.scrape_interval_seconds

    log.info(
        "starting scraper worker, interval=%ss, sources=%s",
        interval,
        [s.name for s in sources],
    )

    publisher = EventPublisher()
    await publisher.start()
    await publisher.emit(make_event("worker_started", message="scraper worker started"))

    source_holder: dict[str, str | None] = {"name": None}

    headers = {
        "User-Agent": settings.scraper_user_agent,
        "Accept-Language": "sl,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml",
    }
    client = httpx.AsyncClient(
        headers=headers,
        follow_redirects=True,
        timeout=httpx.Timeout(30.0),
        event_hooks=_make_http_event_hooks(publisher, source_holder),
    )

    scout_only = len(sources) == 1 and sources[0].name == "bolha.scout"
    if scout_only:
        try:
            await run_all_sources(
                sources, client, publisher, source_holder, reason="startup"
            )
        finally:
            await publisher.emit(
                make_event("worker_stopped", message="scraper worker stopped")
            )
            await client.aclose()
            await publisher.stop()
        log.info("bolha scout finished; worker exiting")
        return

    scheduler = AsyncIOScheduler()

    for source in sources:
        if source.name in _NO_INTERVAL_SOURCES:
            continue
        # add small per-source jitter so we don't hit both at the same instant
        jitter = random.randint(0, max(1, interval // 4))
        trigger = IntervalTrigger(seconds=interval, jitter=jitter)
        scheduler.add_job(
            run_source,
            trigger=trigger,
            args=[source, client, publisher, source_holder],
            id=f"scrape-{source.name}",
            max_instances=1,
            coalesce=True,
            next_run_time=None,  # let scheduler schedule first run after `interval`
            misfire_grace_time=interval,
        )

    scheduler.start()

    stop_event = asyncio.Event()

    background_tasks = [
        asyncio.create_task(heartbeat_loop(publisher, stop_event)),
        asyncio.create_task(
            commands_loop(sources, client, publisher, source_holder, stop_event)
        ),
        # immediate first run for each source
        asyncio.create_task(
            run_all_sources(
                sources, client, publisher, source_holder, reason="startup"
            )
        ),
    ]

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
    for t in background_tasks:
        t.cancel()
    await asyncio.gather(*background_tasks, return_exceptions=True)
    await publisher.emit(make_event("worker_stopped", message="scraper worker stopped"))
    await client.aclose()
    await publisher.stop()
    log.info("scraper worker stopped")


if __name__ == "__main__":
    asyncio.run(main(worker_sources_from_argv(sys.argv[1:])))
