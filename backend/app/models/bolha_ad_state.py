from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class BolhaAdState(Base, TimestampMixin):
    """Pipeline state for bolha integer ad IDs.

    ``status`` is one of: lookahead, pending_fallback, fallback_warming, timed_out, expired.
    ``expired`` means a redirecting listing URL with non-active GTM (removed slot); lookahead
    advances ``last_working_ad_id`` without queuing backfill.
    """

    __tablename__ = "bolha_ad_states"

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
