"""Firecrawl scrape API (cloud or self-hosted)."""

from __future__ import annotations

import logging

import httpx

from scraper.page_fetch import PageFetch

log = logging.getLogger(__name__)

DEFAULT_FIRECRAWL_API_URL = "https://api.firecrawl.dev"
FIRECRAWL_TIMEOUT_SECONDS = 120.0


def scrape_endpoint(api_url: str) -> str:
    base = api_url.rstrip("/")
    if base.endswith("/v2/scrape"):
        return base
    if base.endswith("/v2"):
        return f"{base}/scrape"
    return f"{base}/v2/scrape"


async def fetch_via_firecrawl(
    target_url: str,
    *,
    api_url: str = DEFAULT_FIRECRAWL_API_URL,
    api_key: str | None = None,
    timeout: float = FIRECRAWL_TIMEOUT_SECONDS,
) -> PageFetch:
    endpoint = scrape_endpoint(api_url)
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    httpx_logger = logging.getLogger("httpx")
    prev_level = httpx_logger.level
    httpx_logger.setLevel(logging.WARNING)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                endpoint,
                headers=headers,
                json={
                    "url": target_url,
                    "formats": ["html"],
                    "onlyMainContent": False,
                },
            )
    finally:
        httpx_logger.setLevel(prev_level)

    if resp.status_code >= 400:
        detail = resp.text[:500]
        try:
            payload = resp.json()
            detail = str(payload.get("error") or payload)[:500]
        except Exception:
            pass
        log.warning(
            "firecrawl: API error status=%s endpoint=%s detail=%s",
            resp.status_code,
            endpoint,
            detail,
        )
        return PageFetch(
            text=resp.text,
            status_code=resp.status_code,
            url=target_url,
            headers=resp.headers,
            fetch_mode="firecrawl",
        )

    try:
        payload = resp.json()
    except Exception:
        return PageFetch(
            text=resp.text,
            status_code=502,
            url=target_url,
            headers=resp.headers,
            fetch_mode="firecrawl",
        )

    if not payload.get("success"):
        err = str(payload.get("error") or payload)[:500]
        log.warning("firecrawl: success=false %s", err)
        return PageFetch(
            text=err,
            status_code=502,
            url=target_url,
            headers=resp.headers,
            fetch_mode="firecrawl",
        )

    data = payload.get("data") or {}
    meta = data.get("metadata") or {}
    html = data.get("html") or ""
    page_status = meta.get("statusCode") or meta.get("status") or 200
    try:
        status_code = int(page_status)
    except (TypeError, ValueError):
        status_code = 200

    final_url = meta.get("sourceURL") or meta.get("url") or target_url
    document_title = meta.get("title")
    if isinstance(document_title, str):
        document_title = document_title.strip() or None
    else:
        document_title = None
    return PageFetch(
        text=html,
        status_code=status_code,
        url=final_url,
        headers=resp.headers,
        fetch_mode="firecrawl",
        document_title=document_title,
    )
