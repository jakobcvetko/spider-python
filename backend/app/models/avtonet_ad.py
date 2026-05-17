from sqlalchemy import BigInteger, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

AD_STATUS_PENDING = "pending"
AD_STATUS_SUCCESS = "success"
# Legacy rows may still have "removed"; new scrapes use pending for empty slots.
AD_STATUS_REMOVED = "removed"

SCRAPE_RESULT_SUCCESS = "success"
SCRAPE_RESULT_EMPTY = "empty"
SCRAPE_RESULT_REMOVED = "removed"
SCRAPE_RESULT_ERROR = "error"


class AvtonetAd(Base, TimestampMixin):
    """Persistent registry of every avto.net ad ID probed by lookahead."""

    __tablename__ = "avtonet_ads"

    ad_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    scrape_log: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
