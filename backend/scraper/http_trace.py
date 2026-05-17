"""Payload builders for scraper HTTP trace events (admin live logs)."""

from __future__ import annotations

import uuid
from typing import Any

from scraper.page_fetch import FetchMode


def new_request_id() -> str:
    return uuid.uuid4().hex[:16]


def http_request_data(
    *,
    url: str,
    request_id: str,
    fetch_mode: FetchMode = "direct",
    ad_id: int | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "method": "GET",
        "url": url,
        "fetch_mode": fetch_mode,
        "request_id": request_id,
    }
    if ad_id is not None:
        data["ad_id"] = ad_id
    return data


def http_response_data(
    *,
    url: str,
    request_id: str,
    status: int,
    elapsed_ms: int | None,
    bytes_len: int | None,
    fetch_mode: FetchMode = "direct",
    ad_id: int | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "status": status,
        "method": "GET",
        "url": url,
        "elapsed_ms": elapsed_ms,
        "bytes": bytes_len,
        "fetch_mode": fetch_mode,
        "request_id": request_id,
    }
    if ad_id is not None:
        data["ad_id"] = ad_id
    return data
