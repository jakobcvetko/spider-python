from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AvtonetAdState(Base, TimestampMixin):
    """Pipeline state for avto.net integer ad IDs (mirrors bolha_ad_states)."""

    __tablename__ = "avtonet_ad_states"

    ad_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    last_lookahead_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    first_fallback_scrape_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_fallback_scrape_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_outcome: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
