from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

AD_STATUS_PENDING = "pending"
AD_STATUS_EMPTY = "empty"
AD_STATUS_BACKFILL = "backfill"
AD_STATUS_SUCCESS = "success"
# Legacy rows may still have "removed"; new scrapes use pending for empty slots.
AD_STATUS_REMOVED = "removed"
AD_STATUS_TIMEDOUT = "timed_out"

SCRAPE_RESULT_SUCCESS = "success"
SCRAPE_RESULT_EMPTY = "empty"
SCRAPE_RESULT_REMOVED = "removed"
SCRAPE_RESULT_ERROR = "error"

# Per-scrape result stored in scrape_log entries.
SCRAPE_LOG_MAX_ENTRIES = 50


class AvtonetAd(Base, TimestampMixin):
    """Persistent registry of every avto.net ad ID probed by lookahead."""

    __tablename__ = "avtonet_ads"

    ad_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    backfill_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    scrape_log: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
