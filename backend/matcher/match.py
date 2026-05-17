from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Listing, Scraper, ScraperMatch, User
from app.search_normalize import normalize_text
from app.telegram.notify import NewMatch

log = logging.getLogger(__name__)

BOLHA_SOURCE = "bolha.com"
AVTONET_SOURCE = "avto.net"

_ALL_TOKENS_IN_TITLE = text(
    "NOT EXISTS ("
    "SELECT 1 FROM unnest(scrapers.search_tokens) AS t(token) "
    "WHERE position(t.token IN :normalized_title) = 0"
    ")")


async def _listing_normalized_title(db: AsyncSession, listing: Listing) -> str:
    if listing.title_normalized:
        return listing.title_normalized
    normalized = normalize_text(listing.title)
    listing.title_normalized = normalized
    await db.flush()
    return normalized


async def _scrapers_matching_listing(
    db: AsyncSession,
    listing_source: str,
    normalized_title: str,
) -> list[Scraper]:
    stmt = select(Scraper).where(
        func.cardinality(Scraper.search_tokens) > 0,
        _ALL_TOKENS_IN_TITLE.bindparams(normalized_title=normalized_title),
    )
    if listing_source == BOLHA_SOURCE:
        stmt = stmt.where(Scraper.bolha_enabled.is_(True))
    elif listing_source == AVTONET_SOURCE:
        stmt = stmt.where(Scraper.avtonet_enabled.is_(True))
    else:
        return []
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def match_listing(db: AsyncSession, listing_id: uuid.UUID) -> list[NewMatch]:
    """Check enabled scrapers against listing title tokens; insert new matches."""
    listing = await db.get(Listing, listing_id)
    if listing is None:
        log.warning("matcher: listing %s not found", listing_id)
        return []

    normalized_title = await _listing_normalized_title(db, listing)
    if not normalized_title:
        return []

    matched_scrapers = await _scrapers_matching_listing(db, listing.source, normalized_title)
    if not matched_scrapers:
        return []

    rows = [{"scraper_id": s.id, "listing_id": listing_id} for s in matched_scrapers]
    stmt = (
        pg_insert(ScraperMatch)
        .values(rows)
        .on_conflict_do_nothing(constraint="uq_scraper_matches_scraper_listing")
        .returning(ScraperMatch.scraper_id)
    )
    result = await db.execute(stmt)
    new_scraper_ids = list(result.scalars().all())
    if not new_scraper_ids:
        return []

    log.info(
        "matcher: listing %s (%s) -> %d new match(es)",
        listing_id,
        listing.external_id,
        len(new_scraper_ids),
    )

    scraper_by_id = {s.id: s for s in matched_scrapers if s.id in new_scraper_ids}
    user_ids = {s.user_id for s in scraper_by_id.values()}
    users_result = await db.execute(
        select(User).where(
            User.id.in_(user_ids),
            User.telegram_chat_id.isnot(None),
            User.telegram_notifications_enabled.is_(True),
        )
    )
    users_by_id = {u.id: u for u in users_result.scalars().all()}

    notifications: list[NewMatch] = []
    for scraper_id in new_scraper_ids:
        scraper = scraper_by_id.get(scraper_id)
        if scraper is None:
            continue
        user = users_by_id.get(scraper.user_id)
        if user is None or user.telegram_chat_id is None:
            continue
        notifications.append(
            NewMatch(
                user_id=user.id,
                scraper_name=scraper.name,
                listing=listing,
                telegram_chat_id=user.telegram_chat_id,
            )
        )
    return notifications
