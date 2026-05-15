"""Realtime scraper event bus.

The FastAPI process and the standalone scraper worker live in different OS
processes, so we need IPC to surface scraper activity to admin clients in real
time. We use Postgres ``LISTEN``/``NOTIFY`` because we already require
Postgres + asyncpg and it gives us at-least-once fan-out across processes
without adding Redis or any other broker.

Two channels are used:

* ``scraper_events``   — scraper -> API. Each payload is a JSON event.
* ``scraper_commands`` — API -> scraper. Trigger run-now, etc.

The API process keeps an in-memory ring buffer of the most recent events so
that newly connecting admin WebSocket clients can replay history.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections import deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import asyncpg

from app.config import get_settings

log = logging.getLogger(__name__)

EVENTS_CHANNEL = "scraper_events"
COMMANDS_CHANNEL = "scraper_commands"
RING_BUFFER_SIZE = 200


def _asyncpg_dsn() -> str:
    """Strip the SQLAlchemy ``+driver`` suffix so asyncpg can parse the URL."""
    url = get_settings().database_url
    parts = urlsplit(url)
    scheme = parts.scheme.split("+", 1)[0]  # postgresql+asyncpg -> postgresql
    return urlunsplit((scheme, parts.netloc, parts.path, parts.query, parts.fragment))


def make_event(
    kind: str,
    *,
    source: str | None = None,
    message: str | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": uuid.uuid4().hex,
        "ts": time.time(),
        "kind": kind,
        "source": source,
        "message": message,
        "data": data or {},
    }


async def publish_event(conn: asyncpg.Connection, event: dict[str, Any]) -> None:
    payload = json.dumps(event, default=str)
    # NOTIFY payloads are limited to 8000 bytes — truncate aggressive raw data.
    if len(payload) > 7500:
        trimmed = dict(event)
        trimmed["data"] = {"_truncated": True}
        payload = json.dumps(trimmed, default=str)
    # NOTIFY is a utility statement and doesn't accept bind params; use the
    # pg_notify(text, text) function so we can pass the payload safely.
    await conn.execute("SELECT pg_notify($1, $2)", EVENTS_CHANNEL, payload)


async def send_command(conn: asyncpg.Connection, command: dict[str, Any]) -> None:
    payload = json.dumps(command, default=str)
    await conn.execute("SELECT pg_notify($1, $2)", COMMANDS_CHANNEL, payload)


@asynccontextmanager
async def asyncpg_connection() -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(dsn=_asyncpg_dsn())
    try:
        yield conn
    finally:
        await conn.close()


class ScraperEventBus:
    """In-process subscriber that fans NOTIFY messages out to WS clients.

    Lives in the API process. Maintains:

    * A ring buffer of recent events (so new WS clients see immediate history).
    * A set of asyncio Queues, one per connected WS client.
    * The last heartbeat timestamp (used to compute "scraper connected").
    """

    def __init__(self) -> None:
        self._buffer: deque[dict[str, Any]] = deque(maxlen=RING_BUFFER_SIZE)
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._listener_conn: asyncpg.Connection | None = None
        self._publish_conn: asyncpg.Connection | None = None
        self._publish_lock = asyncio.Lock()
        self._last_heartbeat_ts: float | None = None
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        # Long-lived listener connection
        self._listener_conn = await asyncpg.connect(dsn=_asyncpg_dsn())
        await self._listener_conn.add_listener(EVENTS_CHANNEL, self._on_notify)
        # Separate connection for publishing commands (LISTEN connections shouldn't
        # be used for arbitrary execution from another task).
        self._publish_conn = await asyncpg.connect(dsn=_asyncpg_dsn())
        log.info("scraper event bus started")

    async def stop(self) -> None:
        if not self._started:
            return
        self._started = False
        try:
            if self._listener_conn is not None:
                await self._listener_conn.remove_listener(EVENTS_CHANNEL, self._on_notify)
                await self._listener_conn.close()
        except Exception:  # noqa: BLE001
            log.exception("error stopping listener connection")
        try:
            if self._publish_conn is not None:
                await self._publish_conn.close()
        except Exception:  # noqa: BLE001
            log.exception("error stopping publish connection")
        self._listener_conn = None
        self._publish_conn = None

    def _on_notify(
        self,
        _conn: asyncpg.Connection,
        _pid: int,
        _channel: str,
        payload: str,
    ) -> None:
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            log.warning("dropping malformed scraper event payload: %r", payload[:200])
            return
        if event.get("kind") == "heartbeat":
            ts = event.get("ts")
            if isinstance(ts, (int, float)):
                self._last_heartbeat_ts = float(ts)
        self._buffer.append(event)
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest if a slow client backs up.
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    pass

    def snapshot(self) -> list[dict[str, Any]]:
        return list(self._buffer)

    def last_heartbeat_ts(self) -> float | None:
        return self._last_heartbeat_ts

    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[dict[str, Any]]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=512)
        self._subscribers.add(queue)
        try:
            yield queue
        finally:
            self._subscribers.discard(queue)

    async def send_command(self, command: dict[str, Any]) -> None:
        if self._publish_conn is None:
            raise RuntimeError("event bus not started")
        async with self._publish_lock:
            await send_command(self._publish_conn, command)


_bus: ScraperEventBus | None = None


def get_event_bus() -> ScraperEventBus:
    global _bus
    if _bus is None:
        _bus = ScraperEventBus()
    return _bus
