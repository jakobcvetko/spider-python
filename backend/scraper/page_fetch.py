"""Normalized HTTP page fetch result (direct, ScraperAPI, or Firecrawl)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import httpx

FetchMode = Literal["direct", "scraperapi", "firecrawl"]

EmitFn = Any  # async callable accepting make_event dict; avoids circular imports


@dataclass(frozen=True)
class PageFetch:
    text: str
    status_code: int
    url: str
    headers: httpx.Headers
    fetch_mode: FetchMode = "direct"
    document_title: str | None = None

    @property
    def via_scraperapi(self) -> bool:
        return self.fetch_mode == "scraperapi"

    @property
    def via_proxy(self) -> bool:
        return self.fetch_mode != "direct"


def _trace_request_url(target_url: str, fetch_mode: FetchMode) -> str:
    if fetch_mode == "scraperapi":
        from scraper.scraperapi import SCRAPERAPI_ENDPOINT

        return SCRAPERAPI_ENDPOINT
    if fetch_mode == "firecrawl":
        from app.config import get_settings
        from scraper.firecrawl import scrape_endpoint

        return scrape_endpoint(get_settings().firecrawl_api_url)
    return target_url


async def emit_http_request(
    emit: EmitFn | None,
    *,
    source: str,
    target_url: str,
    request_id: str,
    fetch_mode: FetchMode = "direct",
    ad_id: int | None = None,
) -> None:
    if emit is None:
        return
    from app.scraper_events import make_event
    from scraper.http_trace import http_request_data

    req_url = _trace_request_url(target_url, fetch_mode)
    await emit(
        make_event(
            "http_request",
            source=source,
            message=f"GET {req_url}",
            data=http_request_data(
                url=req_url,
                request_id=request_id,
                fetch_mode=fetch_mode,
                ad_id=ad_id,
            ),
        )
    )


async def emit_http_response(
    emit: EmitFn | None,
    *,
    source: str,
    target_url: str,
    request_id: str,
    status: int,
    elapsed_ms: int | None,
    bytes_len: int | None,
    fetch_mode: FetchMode = "direct",
    ad_id: int | None = None,
) -> None:
    if emit is None:
        return
    from app.scraper_events import make_event
    from scraper.http_trace import http_response_data

    req_url = _trace_request_url(target_url, fetch_mode)
    await emit(
        make_event(
            "http_response",
            source=source,
            message=f"{status} GET {req_url}",
            data=http_response_data(
                url=req_url,
                request_id=request_id,
                status=status,
                elapsed_ms=elapsed_ms,
                bytes_len=bytes_len,
                fetch_mode=fetch_mode,
                ad_id=ad_id,
            ),
        )
    )


async def emit_http_trace(
    emit: EmitFn | None,
    *,
    source: str,
    target_url: str,
    status: int,
    elapsed_ms: int | None,
    bytes_len: int | None,
    fetch_mode: FetchMode = "direct",
    ad_id: int | None = None,
) -> None:
    """Emit paired request+response (used when only the end of a fetch is observed)."""
    from scraper.http_trace import new_request_id

    rid = new_request_id()
    await emit_http_request(
        emit,
        source=source,
        target_url=target_url,
        request_id=rid,
        fetch_mode=fetch_mode,
        ad_id=ad_id,
    )
    await emit_http_response(
        emit,
        source=source,
        target_url=target_url,
        request_id=rid,
        status=status,
        elapsed_ms=elapsed_ms,
        bytes_len=bytes_len,
        fetch_mode=fetch_mode,
        ad_id=ad_id,
    )


def page_from_httpx(resp: httpx.Response, *, fetch_mode: FetchMode = "direct") -> PageFetch:
    return PageFetch(
        text=resp.text,
        status_code=resp.status_code,
        url=str(resp.url),
        headers=resp.headers,
        fetch_mode=fetch_mode,
    )
