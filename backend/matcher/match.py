from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Listing, Scraper, ScraperMatch

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


async def match_listing(db: AsyncSession, listing_id: uuid.UUID) -> int:
    """Check all scrapers against a listing title; insert new matches. Returns insert count."""
    listing = await db.get(Listing, listing_id)
    if listing is None:
        log.warning("matcher: listing %s not found", listing_id)
        return 0

    scrapers = await _scrapers_for_listing_source(db, listing.source)
    if not scrapers:
        return 0

    matched_scraper_ids = [
        s.id
        for s in scrapers
        if _title_matches_scraper_name(listing.title, s.name)
    ]
    if not matched_scraper_ids:
        return 0

    rows = [{"scraper_id": sid, "listing_id": listing_id} for sid in matched_scraper_ids]
    stmt = (
        pg_insert(ScraperMatch)
        .values(rows)
        .on_conflict_do_nothing(constraint="uq_scraper_matches_scraper_listing")
        .returning(ScraperMatch.id)
    )
    result = await db.execute(stmt)
    inserted = len(result.scalars().all())
    if inserted:
        log.info(
            "matcher: listing %s (%s) -> %d new match(es)",
            listing_id,
            listing.external_id,
            inserted,
        )
    return inserted
