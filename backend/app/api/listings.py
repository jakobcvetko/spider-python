from fastapi import APIRouter, Depends, Query
from sqlalchemy import BigInteger, and_, case, cast, desc, nulls_last, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models import Listing, Scraper, ScraperMatch, User
from app.schemas.listing import ListingOut

router = APIRouter(prefix="/listings", tags=["listings"])

BOLHA_SOURCE = "bolha.com"
AVTONET_SOURCE = "avto.net"


def listing_default_order() -> tuple:
    """Lookahead scrapers use monotonic integer ad IDs in ``external_id``."""
    numeric_id = Listing.external_id.op("~")(r"^[0-9]+$")
    bolha_numeric = and_(Listing.source == BOLHA_SOURCE, numeric_id)
    avtonet_numeric = and_(Listing.source == AVTONET_SOURCE, numeric_id)
    ad_id = case(
        (bolha_numeric, cast(Listing.external_id, BigInteger)),
        (avtonet_numeric, cast(Listing.external_id, BigInteger)),
        else_=None,
    )
    return (nulls_last(desc(ad_id)), desc(Listing.created_at))


@router.get("", response_model=list[ListingOut])
async def list_listings(
    source: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Listing]:
    stmt = (
        select(Listing)
        .join(ScraperMatch, ScraperMatch.listing_id == Listing.id)
        .join(Scraper, Scraper.id == ScraperMatch.scraper_id)
        .where(Scraper.user_id == user.id)
        .order_by(*listing_default_order())
        .limit(limit)
    )
    if source:
        stmt = stmt.where(Listing.source == source)
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())
