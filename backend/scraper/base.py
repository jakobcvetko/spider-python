from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Listing

log = logging.getLogger(__name__)


@dataclass
class ScrapedItem:
    """Source-agnostic representation of a single scraped listing."""

    external_id: str
    url: str
    title: str
    price_cents: int | None = None
    currency: str | None = None
    location: str | None = None
    image_url: str | None = None
    year: int | None = None
    mileage_km: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class Source(Protocol):
    """Protocol every scrape source implements."""

    name: str

    async def fetch(self, client: httpx.AsyncClient) -> list[ScrapedItem]: ...


async def upsert_items(
    db: AsyncSession,
    source: str,
    items: list[ScrapedItem],
    *,
    commit: bool = True,
) -> int:
    """Insert items, skipping duplicates by (source, external_id). Returns inserted count."""
    if not items:
        return 0

    rows = [
        {
            "source": source,
            "external_id": item.external_id,
            "url": item.url,
            "title": item.title,
            "price_cents": item.price_cents,
            "currency": item.currency,
            "location": item.location,
            "image_url": item.image_url,
            "year": item.year,
            "mileage_km": item.mileage_km,
            "raw": item.raw or None,
        }
        for item in items
    ]

    stmt = (
        pg_insert(Listing)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["source", "external_id"])
        .returning(Listing.id)
    )
    result = await db.execute(stmt)
    inserted_ids = result.scalars().all()
    if commit:
        await db.commit()
    else:
        await db.flush()
    return len(list(inserted_ids))


def item_to_dict(item: ScrapedItem) -> dict[str, Any]:
    return asdict(item)


async def get_listing_id(
    db: AsyncSession,
    source: str,
    external_id: str,
) -> uuid.UUID | None:
    result = await db.execute(
        select(Listing.id).where(
            Listing.source == source,
            Listing.external_id == external_id,
        )
    )
    return result.scalar_one_or_none()
