"""avto.net detail fetch — direct, ScraperAPI, or Firecrawl."""

from __future__ import annotations

import httpx

from app.config import Settings
from scraper.firecrawl import FIRECRAWL_TIMEOUT_SECONDS, fetch_via_firecrawl
from scraper.page_fetch import FetchMode, PageFetch, page_from_httpx
from scraper.scraperapi import SCRAPERAPI_TIMEOUT_SECONDS, fetch_via_scraperapi

_PROBE_TIMEOUT_SECONDS = 15.0  # avto_net_common.PROBE_TIMEOUT_SECONDS


def resolve_fetch_mode(settings: Settings, override: FetchMode | None = None) -> FetchMode:
    if override is not None:
        return override
    mode = (settings.avtonet_fetch_mode or "auto").strip().lower()
    if mode == "auto":
        if settings.firecrawl_enabled:
            return "firecrawl"
        if settings.scraperapi_enabled:
            return "scraperapi"
        return "direct"
    if mode in ("direct", "scraperapi", "firecrawl"):
        return mode  # type: ignore[return-value]
    return "direct"


def fetch_timeout_seconds(fetch_mode: FetchMode) -> float:
    if fetch_mode == "scraperapi":
        return SCRAPERAPI_TIMEOUT_SECONDS
    if fetch_mode == "firecrawl":
        return FIRECRAWL_TIMEOUT_SECONDS
    return _PROBE_TIMEOUT_SECONDS


async def fetch_detail_page(
    client: httpx.AsyncClient,
    url: str,
    settings: Settings,
    *,
    fetch_mode: FetchMode | None = None,
) -> PageFetch:
    mode = resolve_fetch_mode(settings, fetch_mode)
    if mode == "scraperapi":
        if not settings.scraperapi_api_key:
            raise ValueError("AVTONET_FETCH_MODE=scraperapi but SCRAPERAPI_API_KEY is unset")
        return await fetch_via_scraperapi(
            None,
            url,
            api_key=settings.scraperapi_api_key,
            premium=settings.scraperapi_premium,
            render=settings.scraperapi_render,
            country_code=settings.scraperapi_country_code,
        )
    if mode == "firecrawl":
        if not settings.firecrawl_enabled:
            raise ValueError(
                "AVTONET_FETCH_MODE=firecrawl but neither FIRECRAWL_API_KEY nor "
                "FIRECRAWL_API_URL (self-hosted) is configured"
            )
        return await fetch_via_firecrawl(
            url,
            api_url=settings.firecrawl_api_url,
            api_key=settings.firecrawl_api_key,
        )
    resp = await client.get(url, timeout=_PROBE_TIMEOUT_SECONDS)
    return page_from_httpx(resp, fetch_mode="direct")
