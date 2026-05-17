from __future__ import annotations

import logging
import re
from typing import Literal
from urllib.parse import parse_qs, urlparse

import httpx
from selectolax.parser import HTMLParser

from scraper.base import ScrapedItem
from scraper.http_retries import PROBE_HTTP_RETRIES
from scraper.publish_dates import parse_avtonet_published_at

log = logging.getLogger(__name__)

LISTING_SOURCE = "avto.net"
DETAIL_URL_TEMPLATE = "https://www.avto.net/Ads/details.asp?id={ad_id}"

DEFAULT_START_AD_ID = 22_421_224
# Avtonet lookahead band size (bolha stays at 20 in bolha_common).
LOOKAHEAD_ADS = 5
LOOKAHEAD_BATCH_SIZE = LOOKAHEAD_ADS  # legacy alias
PROBE_DELAY_SECONDS = 0.0
LOOKAHEAD_IDLE_SECONDS = 5.0
PROBE_TIMEOUT_SECONDS = 15.0

# Scout (mirrors bolha_common scout constants).
SCOUT_GALLOP_STEP = 1000
SCOUT_REFINE_STEP = 100
SCOUT_PROBE_WINDOW_RADIUS = 2
SCOUT_PROBE_DELAY_SECONDS = 0.2
SCOUT_PROBE_TIMEOUT_SECONDS = PROBE_TIMEOUT_SECONDS
SCOUT_MAX_PROBES = 500
SCOUT_MAX_ID_SPAN = 2_000_000
SCOUT_HTTP_RETRIES = PROBE_HTTP_RETRIES

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


def _page_title_from_html(html: str) -> str | None:
    tree = HTMLParser(html)
    og = tree.css_first('meta[property="og:title"]')
    if og is not None:
        title = (og.attributes.get("content") or "").strip()
        if title:
            return title
    h1 = tree.css_first("h1")
    if h1 is not None:
        title = h1.text(strip=True)
        if title:
            return title
    t = tree.css_first("title")
    if t is not None:
        title = t.text(strip=True)
        if title:
            return title
    return None


def _title_indicates_missing(title: str) -> bool:
    low = title.strip().lower()
    if low in ("www.avto.net", "avtonet", "avto.net"):
        return True
    if "www.avto.net" not in low:
        return False
    return not (
        re.search(r"letnik\s*:\s*\d{4}", title, re.IGNORECASE)
        or "prodam" in low
        or re.search(r"\d[\d.\s]*\s*eur", title, re.IGNORECASE)
    )


def _title_looks_like_listing(title: str) -> bool:
    if not title or not title.strip():
        return False
    if _title_indicates_missing(title):
        return False
    if re.search(r"letnik\s*:\s*\d{4}", title, re.IGNORECASE):
        return True
    low = title.lower()
    if "prodam" in low and re.search(r"\d", title):
        return True
    if re.search(r"\d[\d.\s]*\s*eur", title, re.IGNORECASE):
        return True
    return False


def classify_detail(
    html: str,
    status: int,
    url: str,
    headers: httpx.Headers,
    *,
    ad_id: int,
    document_title: str | None = None,
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

    title = (document_title or "").strip() or _page_title_from_html(html)
    if title:
        if _title_indicates_missing(title):
            return "not_found", f"generic page title: {title[:80]}"
        if _title_looks_like_listing(title):
            return "active", None

    if status == 200 and _looks_like_active_listing(html):
        return "active", None

    if status == 200:
        return "unknown", "200 but page does not look like a listing"

    return "unknown", f"status {status}"


def classify_detail_response(resp: httpx.Response, *, ad_id: int) -> tuple[ProbeKind, str | None]:
    return classify_detail(
        resp.text,
        resp.status_code,
        str(resp.url),
        resp.headers,
        ad_id=ad_id,
    )


def _looks_like_active_listing(html: str) -> bool:
    title = _page_title_from_html(html)
    return _title_looks_like_listing(title) if title else False


def parse_detail_page(
    html: str,
    ad_id: int,
    *,
    fallback_title: str | None = None,
) -> ScrapedItem:
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
    if not title or _title_indicates_missing(title):
        fb = (fallback_title or "").strip()
        title = (
            fb
            if fb and not _title_indicates_missing(fb)
            else f"Avto.net oglas {ad_id}"
        )

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
        published_at=parse_avtonet_published_at(html),
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
