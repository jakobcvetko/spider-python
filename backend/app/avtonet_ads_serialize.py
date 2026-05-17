"""Serialize ``AvtonetAd`` rows for API responses and scraper WebSocket events."""

from __future__ import annotations

from datetime import datetime, timezone

from app.models.avtonet_ad import AvtonetAd
from app.schemas.admin import AvtonetAdOut, AvtonetAdScrapeEntryOut


def avtonet_ad_to_out(
    row: AvtonetAd,
    *,
    listing_published_at: datetime | None = None,
    listing_created_at: datetime | None = None,
) -> AvtonetAdOut:
    origin = row.created_at
    scrapes: list[AvtonetAdScrapeEntryOut] = []
    for raw in row.scrape_log or []:
        if not isinstance(raw, dict):
            continue
        at_raw = raw.get("at")
        if not at_raw:
            continue
        try:
            at = datetime.fromisoformat(str(at_raw).replace("Z", "+00:00"))
        except ValueError:
            continue
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        offset = (at - origin).total_seconds()
        http_st = raw.get("http_status")
        scrapes.append(
            AvtonetAdScrapeEntryOut(
                offset_seconds=round(offset, 1),
                at=at,
                source=str(raw.get("source", "")),
                result=str(raw.get("result", "")),
                http_status=int(http_st) if http_st is not None else None,
                detail=raw.get("detail"),
            )
        )
    return AvtonetAdOut(
        ad_id=row.ad_id,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
        scrapes=scrapes,
        listing_published_at=listing_published_at,
        listing_created_at=listing_created_at,
    )
