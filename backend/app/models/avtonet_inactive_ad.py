from datetime import datetime

from sqlalchemy import BigInteger, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AvtonetInactiveAd(Base, TimestampMixin):
    """Non-active avto.net ad IDs past the rolling lookahead band (admin UI)."""

    __tablename__ = "avtonet_inactive_ads"

    ad_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    first_inactive_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
