"""Immediate HTTP retries for Bolha / avto.net probe requests."""

from __future__ import annotations

import httpx

PROBE_HTTP_RETRIES = 3


async def httpx_get_with_retries(
    client: httpx.AsyncClient,
    url: str,
    *,
    timeout: float | httpx.Timeout | None = None,
    max_attempts: int = PROBE_HTTP_RETRIES,
) -> httpx.Response:
    """GET *url* up to *max_attempts* times with no backoff between attempts."""
    last_exc: httpx.HTTPError | None = None
    for attempt in range(max_attempts):
        try:
            if timeout is not None:
                return await client.get(url, timeout=timeout)
            return await client.get(url)
        except httpx.HTTPError as exc:
            last_exc = exc
            if attempt + 1 >= max_attempts:
                raise
    assert last_exc is not None
    raise last_exc
