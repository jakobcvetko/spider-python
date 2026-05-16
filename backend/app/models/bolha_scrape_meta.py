from datetime import datetime

from sqlalchemy import BigInteger, DateTime, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BolhaScrapeMeta(Base):
    """Singleton row (id=1) for bolha progressive-scrape UI and cross-run anchor."""

    __tablename__ = "bolha_scrape_meta"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    last_working_ad_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    last_working_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_homepage_max: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    last_homepage_fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_fetch_high_water: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    last_fetch_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
