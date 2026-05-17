"""Helpers for listing ingest / publish timestamps."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Listing


async def listing_times_by_external_ids(
    db: AsyncSession,
    source: str,
    external_ids: list[str],
) -> dict[str, tuple[datetime, datetime | None]]:
    if not external_ids:
        return {}
    result = await db.execute(
        select(
            Listing.external_id,
            Listing.created_at,
            Listing.published_at,
        ).where(
            Listing.source == source,
            Listing.external_id.in_(external_ids),
        )
    )
    return {
        ext_id: (created_at, published_at)
        for ext_id, created_at, published_at in result.all()
    }


async def listing_times_for_external_id(
    db: AsyncSession,
    source: str,
    external_id: str,
) -> tuple[datetime, datetime | None] | None:
    row = (
        await db.execute(
            select(Listing.created_at, Listing.published_at).where(
                Listing.source == source,
                Listing.external_id == external_id,
            )
        )
    ).one_or_none()
    if row is None:
        return None
    return row[0], row[1]


async def listing_times_for_listing_id(
    db: AsyncSession,
    listing_id: UUID,
) -> tuple[datetime, datetime | None] | None:
    row = (
        await db.execute(
            select(Listing.created_at, Listing.published_at).where(Listing.id == listing_id)
        )
    ).one_or_none()
    if row is None:
        return None
    return row[0], row[1]
