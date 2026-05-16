from sqlalchemy import BigInteger, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

# Ad-level status (distinct from bolha_ad_states pipeline statuses).
AD_STATUS_PENDING = "pending"
AD_STATUS_SUCCESS = "success"
AD_STATUS_REMOVED = "removed"

# Per-scrape result stored in scrape_log entries.
SCRAPE_RESULT_SUCCESS = "success"
SCRAPE_RESULT_EMPTY = "empty"
SCRAPE_RESULT_REMOVED = "removed"
SCRAPE_RESULT_ERROR = "error"


class BolhaAd(Base, TimestampMixin):
    """Persistent registry of every bolha ad ID probed by lookahead or backfill."""

    __tablename__ = "bolha_ads"

    ad_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    scrape_log: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
