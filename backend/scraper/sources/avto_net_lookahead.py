"""avto.net ID lookahead — probe sequential detail URLs."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import NoReturn

import httpx

from app.config import Settings, get_settings
from app.database import SessionLocal
from app.matcher_jobs import enqueue_matcher_job
from scraper.avtonet_fetch import fetch_detail_page, fetch_timeout_seconds, resolve_fetch_mode
from scraper.base import ScrapedItem, get_listing_id, upsert_items
from scraper.page_fetch import FetchMode, emit_http_trace
from scraper.sources.avto_net_common import (
    LISTING_SOURCE,
    LOOKAHEAD_BATCH_SIZE,
    LOOKAHEAD_IDLE_SECONDS,
    PROBE_DELAY_SECONDS,
    ProbeKind,
    classify_detail,
    detail_url,
    parse_detail_page,
)
from scraper.sources.avto_net_scout import run_avtonet_scout
from scraper.sources.avtonet_registry import (
    emit_avtonet_progress_tick,
    get_meta,
    meta_begin_batch,
    meta_set_last_working,
    record_avtonet_probe,
)

log = logging.getLogger(__name__)

SOURCE_NAME = "avto.net.lookahead"
EmitFn = Callable[..., Awaitable[None]] | None


@dataclass
class ProbeResult:
    ad_id: int
    http_status: int
    kind: ProbeKind
    detail: str | None
    item: ScrapedItem | None = None
    fetch_mode: FetchMode = "direct"


async def probe_ad_id(
    client: httpx.AsyncClient,
    ad_id: int,
    *,
    settings: Settings | None = None,
    fetch_mode: FetchMode | None = None,
    emit: EmitFn = None,
    source: str = SOURCE_NAME,
) -> ProbeResult:
    settings = settings or get_settings()
    mode = resolve_fetch_mode(settings, fetch_mode)
    url = detail_url(ad_id)
    t0 = time.perf_counter()
    try:
        page = await fetch_detail_page(client, url, settings, fetch_mode=mode)
    except httpx.HTTPError as e:
        log.warning("avto.net lookahead: probe %s failed: %s", ad_id, e)
        elapsed_ms = round((time.perf_counter() - t0) * 1000)
        await emit_http_trace(
            emit,
            source=source,
            target_url=url,
            status=-1,
            elapsed_ms=elapsed_ms,
            bytes_len=None,
            fetch_mode=mode,
        )
        return ProbeResult(
            ad_id=ad_id,
            http_status=-1,
            kind="http_error",
            detail=str(e)[:500],
            fetch_mode=mode,
        )

    elapsed_ms = round((time.perf_counter() - t0) * 1000)
    await emit_http_trace(
        emit,
        source=source,
        target_url=url,
        status=page.status_code,
        elapsed_ms=elapsed_ms,
        bytes_len=len(page.text) if page.text else None,
        fetch_mode=page.fetch_mode,
    )

    kind, detail = classify_detail(
        page.text,
        page.status_code,
        page.url,
        page.headers,
        ad_id=ad_id,
        document_title=page.document_title,
    )
    if page.via_proxy and kind in ("cloudflare", "blocked"):
        detail = (detail or "") + f" (via {page.fetch_mode})"
    item: ScrapedItem | None = None
    if kind == "active":
        item = parse_detail_page(page.text, ad_id)

    return ProbeResult(
        ad_id=ad_id,
        http_status=page.status_code,
        kind=kind,
        detail=detail,
        item=item,
        fetch_mode=page.fetch_mode,
    )


def _log_probe(result: ProbeResult, *, anchor: int) -> None:
    title = result.item.title[:60] if result.item and result.item.title else ""
    extra = f" title={title!r}" if title else ""
    if result.detail:
        extra += f" ({result.detail})"
    log.info(
        "avto.net lookahead: probe id=%s anchor=%s status=%s outcome=%s%s",
        result.ad_id,
        anchor,
        result.http_status,
        result.kind,
        extra,
    )


async def run_lookahead_batch(
    client: httpx.AsyncClient,
    *,
    anchor: int,
    batch_size: int = LOOKAHEAD_BATCH_SIZE,
    delay_seconds: float = PROBE_DELAY_SECONDS,
    emit: EmitFn = None,
    settings: Settings | None = None,
    fetch_mode: FetchMode | None = None,
    persist: bool = True,
) -> tuple[int, list[ProbeResult]]:
    """Probe anchor+1 … anchor+batch_size. Returns (new_anchor, results)."""
    settings = settings or get_settings()
    results: list[ProbeResult] = []
    new_anchor = anchor

    async def _probe_loop(db) -> None:
        nonlocal new_anchor
        for offset in range(1, batch_size + 1):
            if offset > 1 and delay_seconds > 0:
                await asyncio.sleep(delay_seconds)

            ad_id = anchor + offset
            result = await probe_ad_id(
                client,
                ad_id,
                settings=settings,
                fetch_mode=fetch_mode,
                emit=emit,
            )
            results.append(result)
            _log_probe(result, anchor=anchor)
            now = datetime.now(timezone.utc)

            if persist and db is not None:
                await record_avtonet_probe(
                    db,
                    ad_id,
                    source=SOURCE_NAME,
                    kind=result.kind,
                    fetched_at=now,
                    http_status=result.http_status,
                    detail=result.detail,
                    emit=emit,
                )
                await emit_avtonet_progress_tick(
                    emit,
                    scraper_name=SOURCE_NAME,
                    ad_id=ad_id,
                    last_working_ad_id=anchor,
                    outcome=result.kind,
                    http_status=result.http_status,
                )

            if result.kind == "active" and result.item is not None:
                new_anchor = ad_id
                if persist and db is not None:
                    try:
                        await upsert_items(db, LISTING_SOURCE, [result.item])
                    except Exception:
                        log.exception(
                            "avto.net lookahead: upsert failed ad_id=%s", ad_id
                        )
                    listing_id = await get_listing_id(db, LISTING_SOURCE, str(ad_id))
                    if listing_id is not None:
                        try:
                            await enqueue_matcher_job(db, listing_id)
                        except Exception:
                            log.exception(
                                "avto.net lookahead: matcher enqueue failed ad_id=%s",
                                ad_id,
                            )
                    await meta_set_last_working(db, ad_id)
                break

            if result.kind == "not_found":
                new_anchor = ad_id

    if persist:
        async with SessionLocal() as db:
            await meta_begin_batch(db)
            await _probe_loop(db)
            await db.commit()
    else:
        await _probe_loop(None)

    return new_anchor, results


async def run_lookahead_loop(
    client: httpx.AsyncClient,
    *,
    start_anchor: int,
    batch_size: int = LOOKAHEAD_BATCH_SIZE,
    delay_seconds: float = PROBE_DELAY_SECONDS,
    idle_seconds: float = LOOKAHEAD_IDLE_SECONDS,
    emit: EmitFn = None,
    settings: Settings | None = None,
    fetch_mode: FetchMode | None = None,
) -> NoReturn:
    settings = settings or get_settings()
    anchor = start_anchor
    while True:
        async with SessionLocal() as db:
            log.info("avto.net lookahead: running initial scout")
            try:
                await run_avtonet_scout(db, client, emit)
            except RuntimeError:
                log.exception(
                    "avto.net lookahead: initial scout failed; "
                    "continuing with stored anchor"
                )

            meta = await get_meta(db)
            stored = int(meta.last_working_ad_id or 0)
            if stored > 0:
                anchor = stored
            elif anchor <= 0:
                anchor = settings.avtonet_lookahead_start_id

        log.info(
            "avto.net lookahead: batch anchor=%s probing +1..+%s (delay=%ss) fetch=%s",
            anchor,
            batch_size,
            delay_seconds,
            resolve_fetch_mode(settings, fetch_mode),
        )
        anchor, results = await run_lookahead_batch(
            client,
            anchor=anchor,
            batch_size=batch_size,
            delay_seconds=delay_seconds,
            emit=emit,
            settings=settings,
            fetch_mode=fetch_mode,
            persist=True,
        )
        kinds = [r.kind for r in results]
        if kinds and all(k in ("cloudflare", "blocked") for k in kinds):
            log.warning(
                "avto.net lookahead: entire batch blocked/challenged"
            )
        batch_resolved = any(r.kind == "active" for r in results)
        if not batch_resolved:
            await asyncio.sleep(idle_seconds)


class AvtoNetLookaheadSource:
    name = SOURCE_NAME
    listing_source = LISTING_SOURCE

    async def fetch(
        self,
        client: httpx.AsyncClient,
        emit: EmitFn = None,
    ) -> NoReturn:
        settings = get_settings()
        await run_lookahead_loop(
            client,
            start_anchor=settings.avtonet_lookahead_start_id,
            batch_size=settings.avtonet_lookahead_batch_size,
            delay_seconds=settings.avtonet_probe_delay_seconds,
            idle_seconds=settings.avtonet_lookahead_idle_seconds,
            emit=emit,
            settings=settings,
        )


async def _run_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Probe avto.net detail URLs sequentially.",
    )
    parser.add_argument("--start-id", type=int, default=None)
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--delay", type=float, default=None)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument(
        "--fetch-mode",
        choices=("auto", "direct", "scraperapi", "firecrawl"),
        default=None,
    )
    parser.add_argument(
        "--no-scraperapi",
        action="store_true",
        help="Deprecated: same as --fetch-mode direct",
    )
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Skip writing avtonet_ads (HTTP-only smoke test)",
    )
    args = parser.parse_args(argv)
    settings = get_settings()
    anchor = args.start_id if args.start_id is not None else settings.avtonet_lookahead_start_id
    delay = args.delay if args.delay is not None else settings.avtonet_probe_delay_seconds

    headers = {
        "User-Agent": settings.scraper_user_agent,
        "Accept-Language": "sl,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml",
    }
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.no_scraperapi:
        cli_fetch_mode: FetchMode | None = "direct"
    elif args.fetch_mode is not None:
        cli_fetch_mode = args.fetch_mode  # type: ignore[assignment]
    else:
        cli_fetch_mode = None
    mode = resolve_fetch_mode(settings, cli_fetch_mode)
    timeout = fetch_timeout_seconds(mode)

    async with httpx.AsyncClient(
        headers=headers,
        follow_redirects=True,
        timeout=httpx.Timeout(timeout),
    ) as client:
        log.info(
            "avto.net lookahead test: anchor=%s count=%s delay=%ss fetch=%s persist=%s",
            anchor,
            args.count,
            delay,
            mode,
            not args.no_persist,
        )
        if args.loop:
            await run_lookahead_loop(
                client,
                start_anchor=anchor,
                batch_size=args.count,
                delay_seconds=delay,
                settings=settings,
                fetch_mode=cli_fetch_mode,
            )
            return 0

        new_anchor, results = await run_lookahead_batch(
            client,
            anchor=anchor,
            batch_size=args.count,
            delay_seconds=delay,
            settings=settings,
            fetch_mode=cli_fetch_mode,
            persist=not args.no_persist,
        )
        blocked = sum(1 for r in results if r.kind in ("cloudflare", "blocked"))
        active = sum(1 for r in results if r.kind == "active")
        print()
        print(f"Summary @ {datetime.now(timezone.utc).isoformat()}")
        print(f"  anchor in  → {anchor}")
        print(f"  anchor out → {new_anchor}")
        print(f"  active     → {active}")
        print(f"  blocked    → {blocked}")
        for r in results:
            title = f" — {r.item.title[:50]}" if r.item else ""
            print(f"  id={r.ad_id} status={r.http_status} {r.kind}{title}")
        return 0 if active else (2 if blocked else 1)


def main(argv: list[str] | None = None) -> None:
    raise SystemExit(asyncio.run(_run_cli(argv if argv is not None else sys.argv[1:])))


if __name__ == "__main__":
    main()
