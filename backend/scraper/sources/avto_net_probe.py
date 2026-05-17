"""Shared avto.net detail probe (fetch + classify + parse)."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx

from app.config import Settings, get_settings
from scraper.avtonet_fetch import fetch_detail_page, resolve_fetch_mode
from scraper.base import ScrapedItem
from scraper.http_retries import PROBE_HTTP_RETRIES
from scraper.page_fetch import FetchMode, emit_http_trace
from scraper.sources.avto_net_common import (
    ProbeKind,
    classify_detail,
    detail_url,
    parse_detail_page,
)

log = logging.getLogger(__name__)

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
    source: str,
) -> ProbeResult:
    settings = settings or get_settings()
    mode = resolve_fetch_mode(settings, fetch_mode)
    url = detail_url(ad_id)
    t0 = time.perf_counter()
    page = None
    last_exc: httpx.HTTPError | None = None
    for attempt in range(PROBE_HTTP_RETRIES):
        try:
            page = await fetch_detail_page(client, url, settings, fetch_mode=mode)
            break
        except httpx.HTTPError as e:
            last_exc = e
            if attempt + 1 >= PROBE_HTTP_RETRIES:
                log.warning(
                    "avto.net probe %s failed after %s attempts: %s",
                    ad_id,
                    PROBE_HTTP_RETRIES,
                    e,
                )
                elapsed_ms = round((time.perf_counter() - t0) * 1000)
                await emit_http_trace(
                    emit,
                    source=source,
                    target_url=url,
                    status=-1,
                    elapsed_ms=elapsed_ms,
                    bytes_len=None,
                    fetch_mode=mode,
                    ad_id=ad_id,
                )
                return ProbeResult(
                    ad_id=ad_id,
                    http_status=-1,
                    kind="http_error",
                    detail=str(e)[:500],
                    fetch_mode=mode,
                )
    if page is None:
        assert last_exc is not None
        raise last_exc

    elapsed_ms = round((time.perf_counter() - t0) * 1000)
    await emit_http_trace(
        emit,
        source=source,
        target_url=url,
        status=page.status_code,
        elapsed_ms=elapsed_ms,
        bytes_len=len(page.text) if page.text else None,
        fetch_mode=page.fetch_mode,
        ad_id=ad_id,
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
        item = parse_detail_page(
            page.text, ad_id, fallback_title=page.document_title
        )

    return ProbeResult(
        ad_id=ad_id,
        http_status=page.status_code,
        kind=kind,
        detail=detail,
        item=item,
        fetch_mode=page.fetch_mode,
    )
