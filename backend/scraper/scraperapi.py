"""ScraperAPI proxy fetch (https://www.scraperapi.com/)."""

from __future__ import annotations

import json
import logging

import httpx

from scraper.page_fetch import PageFetch

log = logging.getLogger(__name__)

SCRAPERAPI_ENDPOINT = "https://api.scraperapi.com/"
# ScraperAPI retries up to ~70s before returning 500.
SCRAPERAPI_TIMEOUT_SECONDS = 75.0


async def fetch_via_scraperapi(
    _client: httpx.AsyncClient | None,
    target_url: str,
    *,
    api_key: str,
    premium: bool = False,
    render: bool = False,
    country_code: str | None = "si",
    timeout: float = SCRAPERAPI_TIMEOUT_SECONDS,
) -> PageFetch:
    params: dict[str, str] = {
        "api_key": api_key,
        "url": target_url,
    }
    if premium:
        params["premium"] = "true"
    if render:
        params["render"] = "true"
    if country_code:
        params["country_code"] = country_code

    # Do not reuse the worker client — its User-Agent/Accept headers break ScraperAPI.
    httpx_logger = logging.getLogger("httpx")
    prev_level = httpx_logger.level
    httpx_logger.setLevel(logging.WARNING)
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
        ) as api_client:
            resp = await api_client.get(SCRAPERAPI_ENDPOINT, params=params)
    finally:
        httpx_logger.setLevel(prev_level)
    content_type = (resp.headers.get("content-type") or "").lower()

    if resp.status_code >= 400 and "json" in content_type:
        detail = resp.text[:500]
        try:
            payload = json.loads(resp.text)
            detail = str(payload.get("error") or payload)[:500]
        except json.JSONDecodeError:
            pass
        log.warning(
            "scraperapi: API error status=%s detail=%s",
            resp.status_code,
            detail,
        )
        return PageFetch(
            text=resp.text,
            status_code=resp.status_code,
            url=target_url,
            headers=resp.headers,
            fetch_mode="scraperapi",
        )

    # 200 = target body; 404 = target page missing (per ScraperAPI docs).
    return PageFetch(
        text=resp.text,
        status_code=resp.status_code,
        url=target_url,
        headers=resp.headers,
        fetch_mode="scraperapi",
    )
