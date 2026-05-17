from __future__ import annotations

import json
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.matcher_jobs import enqueue_matcher_job
from app.models import BolhaAd, BolhaScrapeMeta
from app.models.bolha_ad import (
    AD_STATUS_BACKFILL,
    AD_STATUS_EMPTY,
    AD_STATUS_PENDING,
    AD_STATUS_REMOVED,
    AD_STATUS_SUCCESS,
    AD_STATUS_TIMEDOUT,
    SCRAPE_LOG_MAX_ENTRIES,
    SCRAPE_RESULT_EMPTY,
    SCRAPE_RESULT_ERROR,
    SCRAPE_RESULT_REMOVED,
    SCRAPE_RESULT_SUCCESS,
)
from app.scraper_events import make_event
from scraper.base import ScrapedItem, get_listing_id, upsert_items
from scraper.http_retries import PROBE_HTTP_RETRIES, httpx_get_with_retries
from scraper.publish_dates import parse_bolha_published_at

log = logging.getLogger(__name__)

EmitFn = Callable[[dict[str, Any]], Awaitable[None]] | None

LISTING_SOURCE = "bolha.com"

IAPI_HOME_URL = "https://iapi.bolha.com/"
AD_PROBE_URL_TEMPLATE = (
    "https://iapi.bolha.com/avtomobili/progressive-scrape-oglas-{ad_id}"
)


def make_probe_client(
    shared: httpx.AsyncClient,
    *,
    timeout_seconds: float,
) -> httpx.AsyncClient:
    """High-volume Bolha probe client; inherits worker HTTP event hooks from *shared*."""
    return httpx.AsyncClient(
        headers=dict(shared.headers),
        follow_redirects=True,
        timeout=httpx.Timeout(timeout_seconds),
        limits=httpx.Limits(max_keepalive_connections=8, max_connections=16),
        event_hooks=shared.event_hooks,
    )

# Lookahead/scout only promote bolha_ads.status to success or empty; everything else stays pending.
FRONTIER_AD_STATUS_SOURCES = frozenset({"bolha.lookahead", "bolha.scout"})
BACKFILL_AD_STATUS_SOURCES = frozenset({"bolha.backfill"})
BACKFILL_PROMOTE_STATUSES = (AD_STATUS_PENDING, AD_STATUS_EMPTY)

LOOKAHEAD_ADS = 10
LOOKAHEAD_TIMEOUT_SECONDS = 5
LOOKAHEAD_PROBE_TIMEOUT_SECONDS = 15.0
# Re-scan listings / homepage occasionally so meta stays aligned with backfill or manual inserts.
LOOKAHEAD_HIGH_WATER_REFRESH_BATCHES = 50
LOOKAHEAD_HOMEPAGE_REFRESH_BATCHES = 120
BACKFILL_CYCLE_PAUSE_SECONDS = 10
BACKFILL_TIMEOUT_SECONDS = 300
BACKFILL_BATCH_SIZE = 5
# Legacy names used by admin / older imports
FALLBACK_CYCLE_PAUSE_SECONDS = BACKFILL_CYCLE_PAUSE_SECONDS
FALLBACK_TIMEOUT_SECONDS = BACKFILL_TIMEOUT_SECONDS
MAX_FALLBACK_IDS_PER_FETCH = BACKFILL_BATCH_SIZE

SCOUT_GALLOP_STEP = 1000
SCOUT_REFINE_STEP = 100
# Gallop/refine/binary bracket high bound (max positive offset in scout window).
SCOUT_PROBE_WINDOW_RADIUS = (LOOKAHEAD_ADS - 1) // 2
SCOUT_PROBE_DELAY_SECONDS = 0.2
SCOUT_PROBE_TIMEOUT_SECONDS = LOOKAHEAD_PROBE_TIMEOUT_SECONDS
SCOUT_MAX_PROBES = 500
SCOUT_MAX_ID_SPAN = 2_000_000
SCOUT_HTTP_RETRIES = PROBE_HTTP_RETRIES

ProbeKind = Literal["active", "not_yet_created", "expired", "not_found", "bad_status"]

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
        published_at=parse_bolha_published_at(html),
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


async def meta_set_homepage_max(db: AsyncSession, hp_max: int) -> None:
    now = datetime.now(timezone.utc)
    await db.execute(
        update(BolhaScrapeMeta)
        .where(BolhaScrapeMeta.id == 1)
        .values(last_homepage_max=hp_max, last_homepage_fetched_at=now)
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


def scrape_result_from_outcome(outcome: str) -> str:
    if outcome == "active":
        return SCRAPE_RESULT_SUCCESS
    if outcome == "expired":
        return SCRAPE_RESULT_REMOVED
    if outcome == "not_yet_created":
        return SCRAPE_RESULT_EMPTY
    return SCRAPE_RESULT_ERROR


def ad_status_from_scrape_result(
    result: str, *, source: str | None = None
) -> str | None:
    if source in FRONTIER_AD_STATUS_SOURCES:
        if result == SCRAPE_RESULT_SUCCESS:
            return AD_STATUS_SUCCESS
        if result == SCRAPE_RESULT_EMPTY:
            return AD_STATUS_EMPTY
        return AD_STATUS_PENDING
    if result == SCRAPE_RESULT_SUCCESS:
        return AD_STATUS_SUCCESS
    if result == SCRAPE_RESULT_REMOVED:
        return AD_STATUS_REMOVED
    if source in BACKFILL_AD_STATUS_SOURCES:
        return None
    return AD_STATUS_PENDING


def merge_ad_status(current: str, new: str) -> str:
    rank = {
        AD_STATUS_PENDING: 0,
        AD_STATUS_EMPTY: 0,
        AD_STATUS_BACKFILL: 1,
        AD_STATUS_REMOVED: 2,
        AD_STATUS_TIMEDOUT: 2,
        AD_STATUS_SUCCESS: 3,
    }
    if rank.get(new, 0) > rank.get(current, 0):
        return new
    return current


async def emit_bolha_ad_update(
    emit: EmitFn,
    row: BolhaAd,
    *,
    source: str,
    scrape_entry: dict[str, Any],
) -> None:
    """Push a compact scrape patch (NOTIFY payload limit is 8 KB)."""
    if emit is None:
        return
    await emit(
        make_event(
            "bolha_ad_update",
            source=source,
            message=f"bolha ad {row.ad_id} updated",
            data={
                "ad_id": int(row.ad_id),
                "status": row.status,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
                "scrape": scrape_entry,
            },
        )
    )


async def record_bolha_ad_scrape(
    db: AsyncSession,
    ad_id: int,
    *,
    source: str,
    result: str,
    fetched_at: datetime,
    http_status: int | None = None,
    detail: str | None = None,
    emit: EmitFn = None,
) -> None:
    """Append a scrape attempt to bolha_ads and update ad-level status."""
    entry: dict[str, Any] = {
        "at": fetched_at.isoformat(),
        "source": source,
        "result": result,
    }
    if http_status is not None:
        entry["http_status"] = http_status
    if detail:
        entry["detail"] = detail[:500]

    resolved = ad_status_from_scrape_result(result, source=source)
    row = await db.get(BolhaAd, ad_id)
    if row is None:
        initial = resolved if resolved is not None else AD_STATUS_PENDING
        row = BolhaAd(ad_id=ad_id, status=initial, scrape_log=[entry])
        db.add(row)
    else:
        log_entries = list(row.scrape_log or [])
        log_entries.append(entry)
        row.scrape_log = log_entries[-SCRAPE_LOG_MAX_ENTRIES:]
        if resolved is not None:
            row.status = merge_ad_status(row.status, resolved)
    await db.flush()
    if emit is not None:
        await db.refresh(row)
        await emit_bolha_ad_update(emit, row, source=source, scrape_entry=entry)


async def record_bolha_ad_scrape_from_outcome(
    db: AsyncSession,
    ad_id: int,
    *,
    source: str,
    outcome: str,
    fetched_at: datetime,
    http_status: int | None = None,
    detail: str | None = None,
    emit: EmitFn = None,
) -> None:
    result = scrape_result_from_outcome(outcome)
    await record_bolha_ad_scrape(
        db,
        ad_id,
        source=source,
        result=result,
        fetched_at=fetched_at,
        http_status=http_status,
        detail=detail,
        emit=emit,
    )


def stayed_on_progressive_scrape_url(resp: httpx.Response, ad_id: int) -> bool:
    """True if the final URL is still the synthetic progressive-scrape page for ``ad_id``.

    Bolha uses two empty-slot shapes: same-URL 404 (ID not published yet) vs canonical redirect
    with GTM ``expired`` (listing slot consumed; listing is gone). GTM ``inactive`` still serves
    a full listing page and is treated as scrape success.
    """
    return f"progressive-scrape-oglas-{ad_id}" in str(resp.url).lower()


def redirected_to_listing_page(resp: httpx.Response, ad_id: int) -> bool:
    """True when Bolha redirected to a category listing URL for this ad id."""
    return f"-oglas-{ad_id}" in str(resp.url).lower()


async def promote_pending_below_to_backfill(
    db: AsyncSession,
    last_working_ad_id: int,
    *,
    now: datetime,
) -> int:
    """Queue gap IDs below a new last_working for bolha.backfill."""
    result = await db.execute(
        update(BolhaAd)
        .where(
            BolhaAd.ad_id < last_working_ad_id,
            BolhaAd.status.in_(BACKFILL_PROMOTE_STATUSES),
        )
        .values(status=AD_STATUS_BACKFILL, backfill_started_at=now)
    )
    await db.flush()
    return int(result.rowcount or 0)


async def activate_last_working_ad(
    db: AsyncSession,
    ad_id: int,
    *,
    html: str,
    source: str,
    emit: EmitFn = None,
    now: datetime | None = None,
) -> int:
    """Store listing, advance meta, queue lower pending/empty IDs for backfill."""
    now = now or datetime.now(timezone.utc)
    item = parse_active_detail(html, ad_id)
    promoted = await promote_pending_below_to_backfill(db, ad_id, now=now)
    await meta_set_last_working(db, ad_id)
    try:
        inserted = await upsert_items(db, LISTING_SOURCE, [item])
    except Exception:
        log.exception("bolha activate_last_working: upsert failed ad_id=%s", ad_id)
        inserted = 0
    listing_id = await get_listing_id(db, LISTING_SOURCE, str(ad_id))
    if listing_id is not None:
        try:
            await enqueue_matcher_job(db, listing_id)
        except Exception:
            log.exception(
                "bolha activate_last_working: matcher enqueue failed ad_id=%s", ad_id
            )
    log.info(
        "bolha activate_last_working: ad_id=%s source=%s promoted=%s inserted=%s",
        ad_id,
        source,
        promoted,
        inserted,
    )
    return inserted


async def finalize_scout_last_working_advance(
    db: AsyncSession,
    probe: httpx.AsyncClient,
    ad_id: int,
    *,
    source_name: str,
    emit: EmitFn = None,
) -> ProbeKind | None:
    """Re-probe highest known id after scout: upsert listing or handle expired slot."""
    url = AD_PROBE_URL_TEMPLATE.format(ad_id=ad_id)
    now = datetime.now(timezone.utc)
    try:
        resp = await httpx_get_with_retries(
            probe,
            url,
            timeout=LOOKAHEAD_PROBE_TIMEOUT_SECONDS,
            max_attempts=SCOUT_HTTP_RETRIES,
        )
    except httpx.HTTPError as e:
        log.warning("bolha scout finalize: probe %s failed: %s", ad_id, e)
        await meta_set_last_working(db, ad_id)
        return None
    html = resp.text
    kind, _gtm, _detail, http_st = classify_probe_response(resp, html, ad_id=ad_id)
    oc = outcome_from_class(kind)
    await record_bolha_ad_scrape_from_outcome(
        db,
        ad_id,
        source=source_name,
        outcome=oc,
        fetched_at=now,
        http_status=http_st,
        emit=emit,
    )
    if kind == "active":
        await activate_last_working_ad(
            db, ad_id, html=html, source=source_name, emit=emit, now=now
        )
        return kind
    if kind == "expired":
        await meta_set_last_working(db, ad_id)
        log.info("bolha scout finalize: expired ad_id=%s, advanced last_working", ad_id)
        return kind
    await meta_set_last_working(db, ad_id)
    return kind


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
        if stayed_on_progressive_scrape_url(resp, ad_id):
            return "not_yet_created", None, None, http_st
        return "not_found", None, None, http_st
    if resp.status_code != 200:
        return "bad_status", None, None, http_st
    gtm = extract_gtm_ad_status(html)
    if gtm in ("active", "inactive") and redirected_to_listing_page(resp, ad_id):
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


def is_known_probe_kind(kind: ProbeKind) -> bool:
    return kind in ("active", "expired")


@dataclass(frozen=True, slots=True)
class ProbeFetchResult:
    ad_id: int
    resp: httpx.Response | None = None
    http_error: str | None = None


async def fetch_probe_http(
    client: httpx.AsyncClient,
    ad_id: int,
) -> ProbeFetchResult:
    """HTTP-only probe fetch (safe to run in parallel; retries on transport errors)."""
    url = AD_PROBE_URL_TEMPLATE.format(ad_id=ad_id)
    try:
        resp = await httpx_get_with_retries(
            client, url, max_attempts=SCOUT_HTTP_RETRIES
        )
        return ProbeFetchResult(ad_id=ad_id, resp=resp)
    except httpx.HTTPError as e:
        return ProbeFetchResult(ad_id=ad_id, http_error=str(e))


async def persist_probe_fetch(
    db: AsyncSession,
    fetch: ProbeFetchResult,
    *,
    source_name: str,
    emit: EmitFn = None,
    last_working_ad_id: int = 0,
    high_water: int = 0,
) -> ProbeKind | None:
    """Persist one probe result. Returns None after unrecoverable HTTP errors."""
    now = datetime.now(timezone.utc)
    ad_id = fetch.ad_id

    if fetch.http_error is not None:
        await record_bolha_ad_scrape(
            db,
            ad_id,
            source=source_name,
            result=SCRAPE_RESULT_ERROR,
            fetched_at=now,
            http_status=-1,
            detail=fetch.http_error,
            emit=emit,
        )
        return None

    assert fetch.resp is not None
    resp = fetch.resp
    html = resp.text
    kind, gtm, _detail, http_st = classify_probe_response(resp, html, ad_id=ad_id)
    oc = outcome_from_class(kind)
    await record_bolha_ad_scrape_from_outcome(
        db,
        ad_id,
        source=source_name,
        outcome=oc,
        fetched_at=now,
        http_status=http_st,
        emit=emit,
    )
    await emit_progress_tick(
        emit,
        scraper_name=source_name,
        ad_id=ad_id,
        last_working_ad_id=last_working_ad_id,
        high_water=high_water,
        outcome=oc,
        http_status=http_st,
        gtm_ad_status=gtm,
    )
    return kind


async def probe_ad_id(
    client: httpx.AsyncClient,
    db: AsyncSession,
    ad_id: int,
    *,
    source_name: str,
    emit: EmitFn = None,
    last_working_ad_id: int = 0,
    high_water: int = 0,
) -> ProbeKind | None:
    """Probe one ad ID; persist probe/scrape rows. Returns None after unrecoverable HTTP errors."""
    for attempt in range(SCOUT_HTTP_RETRIES):
        fetch = await fetch_probe_http(client, ad_id)
        if fetch.http_error is not None:
            log.warning(
                "bolha probe %s failed after %s attempts: %s",
                ad_id,
                SCOUT_HTTP_RETRIES,
                fetch.http_error,
            )
            await persist_probe_fetch(
                db,
                fetch,
                source_name=source_name,
                emit=emit,
                last_working_ad_id=last_working_ad_id,
                high_water=high_water,
            )
            return None

        kind = await persist_probe_fetch(
            db,
            fetch,
            source_name=source_name,
            emit=emit,
            last_working_ad_id=last_working_ad_id,
            high_water=high_water,
        )
        if kind in ("not_found", "bad_status") and attempt + 1 < SCOUT_HTTP_RETRIES:
            continue
        return kind

    return "bad_status"
