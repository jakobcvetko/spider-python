import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models import Scraper, User
from app.schemas.scraper import ScraperCreateIn, ScraperOut, ScraperUpdateIn
from app.search_normalize import sync_scraper_search_tokens
from app.telegram.admin_notify import (
    notify_scraper_created,
    notify_scraper_deleted,
    notify_scraper_updated,
)

router = APIRouter(prefix="/scrapers", tags=["scrapers"])


def _ensure_active_sources(scraper: Scraper) -> None:
    if not scraper.bolha_enabled and not scraper.avtonet_enabled:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Select at least one source",
        )


async def _get_owned_scraper(
    scraper_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> Scraper:
    result = await db.execute(
        select(Scraper).where(Scraper.id == scraper_id, Scraper.user_id == user.id)
    )
    scraper = result.scalar_one_or_none()
    if scraper is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scraper not found")
    return scraper


@router.get("", response_model=list[ScraperOut])
async def list_scrapers(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Scraper]:
    result = await db.execute(
        select(Scraper)
        .where(Scraper.user_id == user.id)
        .order_by(Scraper.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("", response_model=ScraperOut, status_code=status.HTTP_201_CREATED)
async def create_scraper(
    body: ScraperCreateIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Scraper:
    scraper = Scraper(
        user_id=user.id,
        name=body.name.strip(),
        bolha_enabled=body.bolha_enabled,
        avtonet_enabled=body.avtonet_enabled,
    )
    _ensure_active_sources(scraper)
    sync_scraper_search_tokens(scraper)
    db.add(scraper)
    await db.commit()
    await db.refresh(scraper)
    await notify_scraper_created(db, user, scraper)
    return scraper


@router.patch("/{scraper_id}", response_model=ScraperOut)
async def update_scraper(
    scraper_id: uuid.UUID,
    body: ScraperUpdateIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Scraper:
    scraper = await _get_owned_scraper(scraper_id, user, db)
    if body.name is not None:
        scraper.name = body.name.strip()
        sync_scraper_search_tokens(scraper)
    if body.bolha_enabled is not None:
        scraper.bolha_enabled = body.bolha_enabled
    if body.avtonet_enabled is not None:
        scraper.avtonet_enabled = body.avtonet_enabled
    _ensure_active_sources(scraper)
    await db.commit()
    await db.refresh(scraper)
    await notify_scraper_updated(db, user, scraper)
    return scraper


@router.delete("/{scraper_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scraper(
    scraper_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    scraper = await _get_owned_scraper(scraper_id, user, db)
    scraper_name = scraper.name
    await notify_scraper_deleted(db, user, scraper_id=scraper_id, name=scraper_name)
    await db.delete(scraper)
    await db.commit()
