from datetime import datetime

from sqlalchemy import BigInteger, DateTime, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AvtonetScrapeMeta(Base):
    """Singleton row (id=1) for avto.net lookahead anchor."""

    __tablename__ = "avtonet_scrape_meta"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    last_working_ad_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    last_working_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_batch_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
