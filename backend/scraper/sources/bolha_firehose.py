"""Bolha firehose source — JSON:API polling of /ccapi/v3/latest-classifieds.

Replaces brute-force ID enumeration (``bolha.lookahead``) for new-ad discovery.

We mint an anonymous OAuth2 ``client_credentials`` JWT (good for ~6 h) once,
then poll the realtime fire-hose every ~30 s. Each new ad we haven't seen
before is dropped into ``listings`` (basic fields from the JSON), and queued
for backfill via ``bolha_ads.status = 'backfill'`` so ``bolha.backfill`` fills
in description/location/condition by hitting ``iapi.bolha.com``.

Verified end-to-end against live Bolha 2026-05.

See ``docs/BOLHA-API.md`` §8 for the underlying API.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, NoReturn

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal
from app.models import BolhaAd, Listing
from app.models.bolha_ad import (
    AD_STATUS_BACKFILL,
    SCRAPE_LOG_MAX_ENTRIES,
    SCRAPE_RESULT_SUCCESS,
)
from app.scraper_events import make_event
from scraper.base import ScrapedItem, upsert_items
from scraper.sources.bolha_common import (
    EmitFn,
    LISTING_SOURCE,
    emit_bolha_ad_update,
    get_meta,
    meta_begin_fetch,
    meta_set_last_working,
)

log = logging.getLogger(__name__)

# Bolha public OAuth2 client (extracted from www.bolha.com SPA bundle).
# See docs/BOLHA-API.md §1.
OAUTH_TOKEN_URL = "https://www.bolha.com/oauth2/token"
OAUTH_CLIENT_ID = "njuskalo_js_app"
OAUTH_CLIENT_SECRET = "1412aa6f3a6194adefceb8e547d5e6aa"

LATEST_URL = "https://www.bolha.com/ccapi/v3/latest-classifieds"

# Site-wide ad rate is ~5/min on weekend evenings, 0–1/min on quiet times.
# 30 s × page[limit]=200 captures a full hour of arrivals even on a weekend.
FIREHOSE_POLL_SECONDS = 30
FIREHOSE_PAGE_LIMIT = 200

# Refresh JWT 5 min before expiry so a long-running poll can't slip past it.
JWT_REFRESH_MARGIN_SECONDS = 300

# Backoff after a poll failure (HTTP, JSON, etc.). We don't want to
# tight-loop hammering Bolha if anything goes wrong.
FIREHOSE_ERROR_BACKOFF_SECONDS = 60

# httpx's default UA gets flagged by Avalon Insights at /oauth2/token even
# though the data endpoints don't care; play safe everywhere.
CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

_AD_URL_SLUG_RE = re.compile(r"^https?://www\.bolha\.com/([^/]+)/")


def _parse_ad_url_slug(url: str | None) -> str | None:
    if not url:
        return None
    m = _AD_URL_SLUG_RE.match(url)
    return m.group(1) if m else None


def _ad_to_item(ad: dict[str, Any], images: dict[str, str]) -> ScrapedItem | None:
    ad_id_str = str(ad.get("id") or "")
    if not ad_id_str.isdigit():
        return None
    attrs = ad.get("attributes") or {}
    title = (attrs.get("title") or "").strip() or f"Oglas {ad_id_str}"
    url = (attrs.get("adUrl") or "").strip()
    if not url:
        return None

    price_raw = attrs.get("price")
    price_cents: int | None
    currency: str | None
    if isinstance(price_raw, (int, float)):
        price_cents = int(round(float(price_raw) * 100))
        currency = "EUR"
    elif isinstance(price_raw, str) and price_raw.strip().isdigit():
        price_cents = int(price_raw.strip()) * 100
        currency = "EUR"
    else:
        price_cents = None
        currency = None

    rels = ad.get("relationships") or {}
    img_rel = (rels.get("image") or {}).get("data") or {}
    image_id = str(img_rel.get("id") or "") or None
    image_url = images.get(image_id) if image_id else None

    return ScrapedItem(
        external_id=ad_id_str,
        url=url,
        title=title[:500],
        price_cents=price_cents,
        currency=currency,
        location=None,
        image_url=image_url,
        published_at=None,
        raw={
            "mode": "bolha-firehose",
            "ad_id": int(ad_id_str),
            "category_slug": _parse_ad_url_slug(url),
            "image_id": image_id,
        },
    )


async def _existing_external_ids(
    db: AsyncSession, ext_ids: list[str]
) -> set[str]:
    if not ext_ids:
        return set()
    stmt = select(Listing.external_id).where(
        Listing.source == LISTING_SOURCE,
        Listing.external_id.in_(ext_ids),
    )
    res = await db.execute(stmt)
    return {row[0] for row in res.all()}


async def _record_firehose_discovery(
    db: AsyncSession,
    ad_id: int,
    *,
    now: datetime,
    detail: str,
    source: str,
    emit: EmitFn,
) -> bool:
    """Upsert ``bolha_ads`` row marked for backfill enrichment.

    On insert: ``status=backfill`` so the backfill worker picks it up.
    On conflict: append the discovery entry to ``scrape_log``; only promote
    ``pending`` / ``empty`` rows to ``backfill`` — never demote success/removed.
    Returns True iff this was a brand-new ``bolha_ads`` row.
    """
    entry: dict[str, Any] = {
        "at": now.isoformat(),
        "source": source,
        "result": SCRAPE_RESULT_SUCCESS,
        "http_status": 200,
        "detail": detail[:500],
    }

    stmt = (
        pg_insert(BolhaAd)
        .values(
            ad_id=ad_id,
            status=AD_STATUS_BACKFILL,
            backfill_started_at=now,
            scrape_log=[entry],
        )
        .on_conflict_do_nothing(index_elements=["ad_id"])
        .returning(BolhaAd.ad_id)
    )
    res = await db.execute(stmt)
    inserted_id = res.scalar_one_or_none()

    if inserted_id is not None:
        if emit is not None:
            row = await db.get(BolhaAd, ad_id)
            if row is not None:
                await emit_bolha_ad_update(
                    emit, row, source=source, scrape_entry=entry
                )
        return True

    # Conflict path: append to scrape_log; promote pending/empty to backfill,
    # leave success/removed/timed_out alone.
    row = await db.get(BolhaAd, ad_id)
    if row is None:
        # Vanishingly rare race between the no-op insert and the SELECT.
        return False
    log_entries = list(row.scrape_log or [])
    log_entries.append(entry)
    row.scrape_log = log_entries[-SCRAPE_LOG_MAX_ENTRIES:]
    if row.status in ("pending", "empty"):
        row.status = AD_STATUS_BACKFILL
        row.backfill_started_at = now
    await db.flush()
    if emit is not None:
        await emit_bolha_ad_update(emit, row, source=source, scrape_entry=entry)
    return False


class BolhaFirehoseSource:
    name = "bolha.firehose"
    listing_source = LISTING_SOURCE

    def __init__(self) -> None:
        self._jwt: str | None = None
        # monotonic seconds; we refresh `JWT_REFRESH_MARGIN_SECONDS` early
        self._jwt_expires_at: float = 0.0
        self._poll_count = 0

    async def _mint_jwt(self, client: httpx.AsyncClient) -> None:
        resp = await client.post(
            OAUTH_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": OAUTH_CLIENT_ID,
                "client_secret": OAUTH_CLIENT_SECRET,
            },
            headers={
                "User-Agent": CHROME_UA,
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://www.bolha.com",
                "Referer": "https://www.bolha.com/",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            timeout=20.0,
        )
        resp.raise_for_status()
        body = resp.json()
        token = body.get("access_token")
        ttl = int(body.get("expires_in") or 21600)
        if not isinstance(token, str) or len(token) < 50:
            raise RuntimeError(
                f"Bolha JWT mint returned invalid token shape: keys={list(body)}"
            )
        self._jwt = token
        self._jwt_expires_at = time.monotonic() + ttl - JWT_REFRESH_MARGIN_SECONDS
        log.info(
            "bolha firehose: minted JWT, ttl=%ss (refresh in %.0fs)",
            ttl,
            ttl - JWT_REFRESH_MARGIN_SECONDS,
        )

    async def _ensure_jwt(self, client: httpx.AsyncClient) -> str:
        if self._jwt is None or time.monotonic() >= self._jwt_expires_at:
            await self._mint_jwt(client)
        assert self._jwt is not None
        return self._jwt

    async def _poll_latest(
        self, client: httpx.AsyncClient
    ) -> tuple[list[dict[str, Any]], dict[str, str]]:
        token = await self._ensure_jwt(client)
        params = {"include": "image", "page[limit]": str(FIREHOSE_PAGE_LIMIT)}
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.api+json",
            "User-Agent": CHROME_UA,
        }
        resp = await client.get(
            LATEST_URL, params=params, headers=headers, timeout=20.0
        )
        if resp.status_code == 401:
            log.warning("bolha firehose: JWT rejected, re-minting")
            self._jwt = None
            token = await self._ensure_jwt(client)
            headers["Authorization"] = f"Bearer {token}"
            resp = await client.get(
                LATEST_URL, params=params, headers=headers, timeout=20.0
            )
        resp.raise_for_status()
        doc = resp.json()
        images: dict[str, str] = {}
        for inc in doc.get("included") or []:
            if inc.get("type") == "latest-ad-image":
                attrs = inc.get("attributes") or {}
                url = attrs.get("url")
                if isinstance(url, str):
                    images[str(inc.get("id"))] = url
        return list(doc.get("data") or []), images

    async def _process_batch(
        self,
        db: AsyncSession,
        ads: list[dict[str, Any]],
        images: dict[str, str],
        *,
        emit: EmitFn,
    ) -> tuple[int, int, int | None]:
        """Returns (parsed_listings, new_listings_inserted, max_id)."""
        if not ads:
            return 0, 0, None

        items: list[ScrapedItem] = []
        for ad in ads:
            item = _ad_to_item(ad, images)
            if item is not None:
                items.append(item)
        if not items:
            return 0, 0, None

        ext_ids = [i.external_id for i in items]
        max_id = max(int(eid) for eid in ext_ids)
        existing = await _existing_external_ids(db, ext_ids)
        new_items = [i for i in items if i.external_id not in existing]
        now = datetime.now(timezone.utc)

        inserted = 0
        if new_items:
            inserted = await upsert_items(
                db, LISTING_SOURCE, new_items, commit=False
            )
            for item in new_items:
                ad_id_int = int(item.external_id)
                await _record_firehose_discovery(
                    db,
                    ad_id_int,
                    now=now,
                    detail=f"firehose discovery (latest-classifieds): {item.title[:80]}",
                    source=self.name,
                    emit=emit,
                )

        return len(items), inserted, max_id

    async def fetch(
        self,
        client: httpx.AsyncClient,
        emit: EmitFn = None,
    ) -> NoReturn:
        """Runs until process exit. Handles its own polling + JWT lifecycle."""
        try:
            await self._mint_jwt(client)
        except httpx.HTTPError:
            log.exception(
                "bolha firehose: initial JWT mint failed; will retry next poll"
            )

        while True:
            self._poll_count += 1
            try:
                ads, images = await self._poll_latest(client)
            except (httpx.HTTPError, RuntimeError) as e:
                log.warning("bolha firehose: poll failed: %s", e)
                if emit is not None:
                    await emit(
                        make_event(
                            "fetch_error",
                            source=self.name,
                            message=f"poll failed: {type(e).__name__}: {e}",
                        )
                    )
                await asyncio.sleep(FIREHOSE_ERROR_BACKOFF_SECONDS)
                continue

            try:
                async with SessionLocal() as db:
                    meta = await get_meta(db)
                    anchor = int(meta.last_working_ad_id or 0)
                    parsed, inserted, max_id = await self._process_batch(
                        db, ads, images, emit=emit
                    )
                    high = max(anchor, max_id or 0)
                    if max_id is not None and max_id > anchor:
                        await meta_set_last_working(db, max_id)
                    await meta_begin_fetch(db, high=high)
                    await db.commit()
            except Exception as e:  # noqa: BLE001
                log.exception("bolha firehose: db batch failed")
                if emit is not None:
                    await emit(
                        make_event(
                            "fetch_error",
                            source=self.name,
                            message=f"db batch failed: {type(e).__name__}: {e}",
                        )
                    )
                await asyncio.sleep(FIREHOSE_ERROR_BACKOFF_SECONDS)
                continue

            log.info(
                "bolha firehose: poll #%d → %d ads parsed, %d new listings, "
                "max_id=%s (anchor was %s)",
                self._poll_count,
                parsed,
                inserted,
                max_id,
                anchor,
            )
            if emit is not None:
                await emit(
                    make_event(
                        "bolha_firehose_poll",
                        source=self.name,
                        message=(
                            f"poll #{self._poll_count}: parsed {parsed}, "
                            f"{inserted} new, max_id={max_id}"
                        ),
                        data={
                            "poll": self._poll_count,
                            "parsed": parsed,
                            "new_listings": inserted,
                            "max_id": max_id,
                            "anchor": anchor,
                        },
                    )
                )

            await asyncio.sleep(FIREHOSE_POLL_SECONDS)
