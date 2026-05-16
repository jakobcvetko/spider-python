from __future__ import annotations

import json
import logging
import re
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
from sqlalchemy import delete, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BolhaAdProbe, BolhaAdState, BolhaScrapeMeta
from app.scraper_events import make_event
from scraper.base import ScrapedItem

log = logging.getLogger(__name__)

EmitFn = Callable[[dict[str, Any]], Awaitable[None]] | None

LISTING_SOURCE = "bolha.com"

IAPI_HOME_URL = "https://iapi.bolha.com/"
AD_PROBE_URL_TEMPLATE = (
    "https://iapi.bolha.com/avtomobili/progressive-scrape-oglas-{ad_id}"
)

LOOKAHEAD_ADS = 20
LOOKAHEAD_TIMEOUT_SECONDS = 5
FALLBACK_CYCLE_PAUSE_SECONDS = 10
FALLBACK_TIMEOUT_SECONDS = 60
AD_TIMEOUT_SECONDS = FALLBACK_TIMEOUT_SECONDS

MAX_FALLBACK_IDS_PER_FETCH = 40

STATUS_LOOKAHEAD = "lookahead"
STATUS_PENDING_FALLBACK = "pending_fallback"
STATUS_FALLBACK_WARMING = "fallback_warming"
STATUS_TIMED_OUT = "timed_out"
STATUS_EXPIRED = "expired"

ID_IN_PAGE_RE = re.compile(r"-oglas-(\d+)", re.IGNORECASE)


def _parse_price_cents(text: str | None) -> tuple[int | None, str | None]:
    if not text:
        return None, None
    cur = "EUR" if "€" in text or "EUR" in text.upper() else None
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return None, cur
    try:
        return int(digits) * 100, cur
    except ValueError:
        return None, cur


def max_ad_id_from_homepage_html(html: str) -> int:
    ids = [int(x) for x in ID_IN_PAGE_RE.findall(html)]
    return max(ids) if ids else 0


def extract_gtm_ad_status(html: str) -> str | None:
    idx = html.find('"name":"GTMTracking"')
    if idx == -1:
        return None
    chunk = html[idx : idx + 2500]
    m = re.search(r'"adStatus"\s*:\s*"([^"]+)"', chunk)
    return m.group(1) if m else None


def parse_active_detail(html: str, ad_id: int) -> ScrapedItem:
    title_m = re.search(r'<meta property="og:title" content="([^"]*)"', html)
    title = (title_m.group(1).strip() if title_m else "") or f"Oglas {ad_id}"
    title = title[:500]

    url_m = re.search(r'<link rel="canonical" href="([^"]+)"', html)
    url = (url_m.group(1).strip() if url_m else "") or AD_PROBE_URL_TEMPLATE.format(
        ad_id=ad_id
    )

    img_m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
    image_url = img_m.group(1).strip() if img_m else None

    price_cents: int | None = None
    currency: str | None = None
    pm = re.search(r'"price"\s*:\s*"((?:[^"\\]|\\.)*)"', html)
    if pm:
        try:
            decoded = json.loads(f'"{pm.group(1)}"')
            price_cents, currency = _parse_price_cents(decoded)
        except json.JSONDecodeError:
            price_cents, currency = _parse_price_cents(pm.group(1))

    return ScrapedItem(
        external_id=str(ad_id),
        url=url,
        title=title,
        price_cents=price_cents,
        currency=currency,
        location=None,
        image_url=image_url,
        raw={
            "mode": "bolha-progressive",
            "ad_id": ad_id,
            "probe_url": AD_PROBE_URL_TEMPLATE.format(ad_id=ad_id),
        },
    )


async def get_meta(db: AsyncSession) -> BolhaScrapeMeta:
    row = await db.get(BolhaScrapeMeta, 1)
    if row is None:
        row = BolhaScrapeMeta(id=1)
        db.add(row)
        await db.flush()
    return row


async def meta_begin_fetch(db: AsyncSession, *, high: int) -> None:
    now = datetime.now(timezone.utc)
    await db.execute(
        update(BolhaScrapeMeta)
        .where(BolhaScrapeMeta.id == 1)
        .values(
            last_fetch_high_water=high,
            last_fetch_started_at=now,
        )
    )
    await db.flush()


async def meta_set_last_working(db: AsyncSession, ad_id: int) -> None:
    now = datetime.now(timezone.utc)
    await db.execute(
        update(BolhaScrapeMeta)
        .where(BolhaScrapeMeta.id == 1)
        .values(last_working_ad_id=ad_id, last_working_at=now)
    )
    await db.flush()


async def max_numeric_listing_id(db: AsyncSession) -> int:
    r = await db.execute(
        text(
            """
            SELECT MAX(CAST(external_id AS BIGINT))
            FROM listings
            WHERE source = :src AND external_id ~ '^[0-9]+$'
            """
        ),
        {"src": LISTING_SOURCE},
    )
    v = r.scalar_one_or_none()
    return int(v) if v is not None else 0


async def upsert_probe(
    db: AsyncSession,
    ad_id: int,
    *,
    fetched_at: datetime,
    http_status: int,
    gtm_ad_status: str | None,
    outcome: str,
    detail: str | None = None,
) -> None:
    stmt = (
        insert(BolhaAdProbe)
        .values(
            ad_id=ad_id,
            fetched_at=fetched_at,
            http_status=http_status,
            gtm_ad_status=gtm_ad_status,
            outcome=outcome,
            detail=detail,
        )
        .on_conflict_do_update(
            index_elements=[BolhaAdProbe.ad_id],
            set_={
                "fetched_at": fetched_at,
                "http_status": http_status,
                "gtm_ad_status": gtm_ad_status,
                "outcome": outcome,
                "detail": detail,
            },
        )
    )
    await db.execute(stmt)
    await db.flush()


async def upsert_lookahead_state(
    db: AsyncSession,
    ad_id: int,
    *,
    now: datetime,
    last_outcome: str,
    detail: str | None = None,
) -> None:
    stmt = (
        insert(BolhaAdState)
        .values(
            ad_id=ad_id,
            status=STATUS_LOOKAHEAD,
            last_lookahead_at=now,
            last_outcome=last_outcome,
            last_detail=detail,
        )
        .on_conflict_do_update(
            index_elements=[BolhaAdState.ad_id],
            set_={
                "status": STATUS_LOOKAHEAD,
                "last_lookahead_at": now,
                "last_outcome": last_outcome,
                "last_detail": detail,
            },
        )
    )
    await db.execute(stmt)
    await db.flush()


def stayed_on_progressive_scrape_url(resp: httpx.Response, ad_id: int) -> bool:
    """True if the final URL is still the synthetic progressive-scrape page for ``ad_id``.

    Bolha uses two inactive shapes: same-URL (ID not published yet) vs canonical redirect
    (listing existed; slot is expired/offline). Only the latter advances ``last_working_ad_id``
    without queuing backfill.
    """
    return f"progressive-scrape-oglas-{ad_id}" in str(resp.url).lower()


async def delete_lookahead_below_ad(db: AsyncSession, before_ad_id: int) -> None:
    """Drop lookahead rows strictly below a new boundary (e.g. confirmed expired id)."""
    await db.execute(
        delete(BolhaAdState).where(
            BolhaAdState.ad_id < before_ad_id,
            BolhaAdState.status == STATUS_LOOKAHEAD,
        )
    )
    await db.flush()


async def upsert_expired_state(
    db: AsyncSession,
    ad_id: int,
    *,
    now: datetime,
    last_outcome: str,
    detail: str | None = None,
) -> None:
    stmt = (
        insert(BolhaAdState)
        .values(
            ad_id=ad_id,
            status=STATUS_EXPIRED,
            last_lookahead_at=now,
            first_fallback_scrape_at=None,
            last_fallback_scrape_at=None,
            last_outcome=last_outcome,
            last_detail=detail,
        )
        .on_conflict_do_update(
            index_elements=[BolhaAdState.ad_id],
            set_={
                "status": STATUS_EXPIRED,
                "last_lookahead_at": now,
                "first_fallback_scrape_at": None,
                "last_fallback_scrape_at": None,
                "last_outcome": last_outcome,
                "last_detail": detail,
            },
        )
    )
    await db.execute(stmt)
    await db.flush()


async def promote_lookahead_below_to_pending_fallback(
    db: AsyncSession,
    found_ad_id: int,
    *,
    now: datetime,
) -> None:
    """Queue existing lookahead rows below found_ad_id for the backfill scraper."""
    await db.execute(
        update(BolhaAdState)
        .where(
            BolhaAdState.ad_id < found_ad_id,
            BolhaAdState.status == STATUS_LOOKAHEAD,
        )
        .values(
            status=STATUS_PENDING_FALLBACK,
            first_fallback_scrape_at=now,
            last_lookahead_at=None,
            last_outcome=None,
            last_detail=None,
        )
    )
    await db.flush()


async def delete_ad_state(db: AsyncSession, ad_id: int) -> None:
    await db.execute(delete(BolhaAdState).where(BolhaAdState.ad_id == ad_id))
    await db.flush()


async def emit_progress_tick(
    emit: EmitFn,
    *,
    scraper_name: str,
    ad_id: int,
    last_working_ad_id: int,
    high_water: int,
    outcome: str,
    http_status: int,
    gtm_ad_status: str | None,
) -> None:
    if emit is None:
        return
    await emit(
        make_event(
            "bolha_progressive_tick",
            source=scraper_name,
            message=f"probe {ad_id} → {outcome}",
            data={
                "ad_id": ad_id,
                "last_working_ad_id": last_working_ad_id,
                "high_water": high_water,
                "outcome": outcome,
                "http_status": http_status,
                "gtm_ad_status": gtm_ad_status,
            },
        )
    )


def classify_probe_response(
    resp: httpx.Response,
    html: str,
    *,
    ad_id: int,
) -> tuple[
    Literal["active", "not_yet_created", "expired", "not_found", "bad_status"],
    str | None,
    str | None,
    int,
]:
    http_st = resp.status_code
    if resp.status_code == 404:
        return "not_found", None, None, http_st
    if resp.status_code != 200:
        return "bad_status", None, None, http_st
    gtm = extract_gtm_ad_status(html)
    if gtm == "active":
        return "active", gtm, None, http_st
    if stayed_on_progressive_scrape_url(resp, ad_id):
        return "not_yet_created", gtm, None, http_st
    return "expired", gtm, None, http_st


def outcome_from_class(
    kind: Literal["active", "not_yet_created", "expired", "not_found", "bad_status"],
) -> str:
    return {
        "active": "active",
        "not_yet_created": "not_yet_created",
        "expired": "expired",
        "not_found": "not_found",
        "bad_status": "bad_http_status",
    }[kind]
