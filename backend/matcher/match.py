from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Listing, Scraper, ScraperMatch, User
from app.telegram.notify import NewMatch

log = logging.getLogger(__name__)

BOLHA_SOURCE = "bolha.com"
AVTONET_SOURCE = "avto.net"


def _title_matches_scraper_name(title: str, scraper_name: str) -> bool:
    name = scraper_name.strip()
    if not name:
        return False
    return name.casefold() in title.casefold()


async def _scrapers_for_listing_source(
    db: AsyncSession,
    listing_source: str,
) -> list[Scraper]:
    stmt = select(Scraper)
    if listing_source == BOLHA_SOURCE:
        stmt = stmt.where(Scraper.bolha_enabled.is_(True))
    elif listing_source == AVTONET_SOURCE:
        stmt = stmt.where(Scraper.avtonet_enabled.is_(True))
    else:
        return []
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def match_listing(db: AsyncSession, listing_id: uuid.UUID) -> list[NewMatch]:
    """Check all scrapers against a listing title; insert new matches. Returns notify targets."""
    listing = await db.get(Listing, listing_id)
    if listing is None:
        log.warning("matcher: listing %s not found", listing_id)
        return []

    scrapers = await _scrapers_for_listing_source(db, listing.source)
    if not scrapers:
        return []

    matched_scrapers = [
        s for s in scrapers if _title_matches_scraper_name(listing.title, s.name)
    ]
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
