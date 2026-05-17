from __future__ import annotations

import logging
import re
from typing import Literal
from urllib.parse import parse_qs, urlparse

import httpx
from selectolax.parser import HTMLParser

from scraper.base import ScrapedItem

log = logging.getLogger(__name__)

LISTING_SOURCE = "avto.net"
DETAIL_URL_TEMPLATE = "https://www.avto.net/Ads/details.asp?id={ad_id}"

DEFAULT_START_AD_ID = 22_421_224
# Match bolha.lookahead (bolha_common.LOOKAHEAD_ADS / LOOKAHEAD_TIMEOUT_SECONDS).
LOOKAHEAD_BATCH_SIZE = 20
PROBE_DELAY_SECONDS = 0.0
LOOKAHEAD_IDLE_SECONDS = 5.0
PROBE_TIMEOUT_SECONDS = 15.0

# Scout (mirrors bolha_common scout constants).
SCOUT_GALLOP_STEP = 1000
SCOUT_REFINE_STEP = 100
SCOUT_PROBE_DELAY_SECONDS = 0.2
SCOUT_PROBE_TIMEOUT_SECONDS = PROBE_TIMEOUT_SECONDS
SCOUT_MAX_PROBES = 500
SCOUT_MAX_ID_SPAN = 2_000_000
SCOUT_HTTP_RETRIES = 3

ProbeKind = Literal[
    "active",
    "cloudflare",
    "not_found",
    "blocked",
    "redirect",
    "http_error",
    "unknown",
]

_CHALLENGE_MARKERS = (
    "just a moment",
    "cf-browser-verification",
    "challenge-platform",
    "enable javascript and cookies",
)


def detail_url(ad_id: int) -> str:
    return DETAIL_URL_TEMPLATE.format(ad_id=ad_id)


def _is_challenge_page(html: str, headers: httpx.Headers) -> bool:
    if (headers.get("cf-mitigated") or "").lower() == "challenge":
        return True
    low = html[:8000].lower()
    return any(m in low for m in _CHALLENGE_MARKERS)


def classify_detail(
    html: str,
    status: int,
    url: str,
    headers: httpx.Headers,
    *,
    ad_id: int,
) -> tuple[ProbeKind, str | None]:
    """Classify a detail-page probe (status + body heuristics)."""
    final_host = urlparse(url).netloc.lower()

    if status == 404:
        return "not_found", None
    if status in (410, 451):
        return "not_found", None

    if _is_challenge_page(html, headers):
        return "cloudflare", "cloudflare challenge page"

    if status == 403:
        return "blocked", "403 forbidden"

    if status >= 500:
        return "http_error", f"server error {status}"

    if status >= 400:
        return "blocked", f"client error {status}"

    if "details.asp" not in url.lower() and final_host.endswith("avto.net"):
        return "redirect", f"final url {url}"

    if status == 200 and _looks_like_active_listing(html):
        return "active", None

    if status == 200:
        return "unknown", "200 but page does not look like a listing"

    return "unknown", f"status {status}"


def classify_detail_response(resp: httpx.Response, *, ad_id: int) -> tuple[ProbeKind, str | None]:
    return classify_detail(resp.text, resp.status_code, str(resp.url), resp.headers, ad_id=ad_id)


def _looks_like_active_listing(html: str) -> bool:
    low = html[:120_000].lower()
    if "details.asp" in low and ("oglas" in low or "znamka" in low or "letnik" in low):
        return True
    tree = HTMLParser(html)
    if tree.css_first("h1"):
        return True
    og = tree.css_first('meta[property="og:title"]')
    if og is not None and (og.attributes.get("content") or "").strip():
        return True
    return False


def parse_detail_page(html: str, ad_id: int) -> ScrapedItem | None:
    tree = HTMLParser(html)
    title = None
    og = tree.css_first('meta[property="og:title"]')
    if og is not None:
        title = (og.attributes.get("content") or "").strip()
    if not title:
        h1 = tree.css_first("h1")
        title = h1.text(strip=True) if h1 else None
    if not title:
        t = tree.css_first("title")
        title = t.text(strip=True) if t else None
    if not title:
        return None

    price_cents: int | None = None
    currency: str | None = "EUR"
    price_match = re.search(
        r"(\d[\d\.\s]*)\s*€|cena[^<]{0,40}?(\d[\d\.\s]*)",
        html[:80_000],
        re.IGNORECASE,
    )
    if price_match:
        raw = price_match.group(1) or price_match.group(2) or ""
        digits = "".join(ch for ch in raw if ch.isdigit())
        if digits:
            price_cents = int(digits) * 100

    year = None
    year_match = re.search(r"\b(19|20)\d{2}\b", title)
    if year_match:
        year = int(year_match.group(0))

    return ScrapedItem(
        external_id=str(ad_id),
        url=detail_url(ad_id),
        title=title[:500],
        price_cents=price_cents,
        currency=currency,
        raw={"probe": "detail"},
        year=year,
    )


def external_id_from_url(url: str) -> int | None:
    qs = parse_qs(urlparse(url).query)
    raw = (qs.get("id") or [None])[0]
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None
