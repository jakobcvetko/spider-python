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


async def emit_http_trace(
    emit: EmitFn | None,
    *,
    source: str,
    target_url: str,
    status: int,
    elapsed_ms: int | None,
    bytes_len: int | None,
    fetch_mode: FetchMode = "direct",
) -> None:
    if emit is None:
        return
    from app.scraper_events import make_event

    if fetch_mode == "scraperapi":
        from scraper.scraperapi import SCRAPERAPI_ENDPOINT

        req_url = SCRAPERAPI_ENDPOINT
    elif fetch_mode == "firecrawl":
        from app.config import get_settings
        from scraper.firecrawl import scrape_endpoint

        req_url = scrape_endpoint(get_settings().firecrawl_api_url)
    else:
        req_url = target_url
    await emit(
        make_event(
            "http_request",
            source=source,
            message=f"GET {req_url}",
            data={"method": "GET", "url": req_url, "fetch_mode": fetch_mode},
        )
    )
    await emit(
        make_event(
            "http_response",
            source=source,
            message=f"{status} GET {req_url}",
            data={
                "status": status,
                "method": "GET",
                "url": req_url,
                "elapsed_ms": elapsed_ms,
                "bytes": bytes_len,
                "fetch_mode": fetch_mode,
            },
        )
    )


def page_from_httpx(resp: httpx.Response, *, fetch_mode: FetchMode = "direct") -> PageFetch:
    return PageFetch(
        text=resp.text,
        status_code=resp.status_code,
        url=str(resp.url),
        headers=resp.headers,
        fetch_mode=fetch_mode,
    )
