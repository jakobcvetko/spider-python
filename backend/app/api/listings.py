from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models import Listing, User
from app.schemas.listing import ListingOut

router = APIRouter(prefix="/listings", tags=["listings"])


@router.get("", response_model=list[ListingOut])
async def list_listings(
    source: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Listing]:
    stmt = select(Listing).order_by(Listing.created_at.desc()).limit(limit)
    if source:
        stmt = stmt.where(Listing.source == source)
    result = await db.execute(stmt)
    return list(result.scalars().all())
