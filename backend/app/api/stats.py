from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models import Scraper, ScraperMatch, User
from app.schemas.stats import DailyMatchCountOut, DailyMatchesOut

router = APIRouter(prefix="/stats", tags=["stats"])

DEFAULT_DAYS = 14
MAX_DAYS = 90


@router.get("/daily-matches", response_model=DailyMatchesOut)
async def daily_matches(
    days: int = Query(default=DEFAULT_DAYS, ge=1, le=MAX_DAYS),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DailyMatchesOut:
    today = datetime.now(UTC).date()
    start_date = today - timedelta(days=days - 1)
    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=UTC)

    day_col = func.date_trunc("day", ScraperMatch.created_at).label("day")
    stmt = (
        select(day_col, func.count().label("count"))
        .join(Scraper, Scraper.id == ScraperMatch.scraper_id)
        .where(
            Scraper.user_id == user.id,
            ScraperMatch.created_at >= start_dt,
        )
        .group_by(day_col)
        .order_by(day_col)
    )
    result = await db.execute(stmt)
    counts_by_day: dict[date, int] = {}
    for row in result.all():
        day_value = row.day
        if hasattr(day_value, "date"):
            day_key = day_value.date()
        else:
            day_key = day_value
        counts_by_day[day_key] = int(row.count)

    out_days: list[DailyMatchCountOut] = []
    total = 0
    for offset in range(days):
        d = start_date + timedelta(days=offset)
        count = counts_by_day.get(d, 0)
        total += count
        out_days.append(DailyMatchCountOut(date=d, count=count))

    return DailyMatchesOut(days=out_days, total=total)
