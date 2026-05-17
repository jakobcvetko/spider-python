"""ScraperAPI proxy fetch (https://www.scraperapi.com/)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger(__name__)

SCRAPERAPI_ENDPOINT = "https://api.scraperapi.com/"
# ScraperAPI retries up to ~70s before returning 500.
SCRAPERAPI_TIMEOUT_SECONDS = 75.0

EmitFn = Any  # async callable accepting make_event dict; avoids circular imports


@dataclass(frozen=True)
class PageFetch:
    """Normalized page body + status for classification (direct or via ScraperAPI)."""

    text: str
    status_code: int
    url: str
    headers: httpx.Headers
    via_scraperapi: bool = False


async def emit_http_trace(
    emit: EmitFn | None,
    *,
    source: str,
    target_url: str,
    status: int,
    elapsed_ms: int | None,
    bytes_len: int | None,
    via_scraperapi: bool = False,
) -> None:
    if emit is None:
        return
    from app.scraper_events import make_event

    req_url = SCRAPERAPI_ENDPOINT if via_scraperapi else target_url
    await emit(
        make_event(
            "http_request",
            source=source,
            message=f"GET {req_url}",
            data={"method": "GET", "url": req_url},
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
            },
        )
    )


def page_from_httpx(resp: httpx.Response) -> PageFetch:
    return PageFetch(
        text=resp.text,
        status_code=resp.status_code,
        url=str(resp.url),
        headers=resp.headers,
    )


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
            via_scraperapi=True,
        )

    # 200 = target body; 404 = target page missing (per ScraperAPI docs).
    return PageFetch(
        text=resp.text,
        status_code=resp.status_code,
        url=target_url,
        headers=resp.headers,
        via_scraperapi=True,
    )
