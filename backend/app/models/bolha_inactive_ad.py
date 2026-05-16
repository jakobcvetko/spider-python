from datetime import datetime

from sqlalchemy import BigInteger, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class BolhaInactiveAd(Base, TimestampMixin):
    """Tracks bolha.com ad IDs seen as non-active **past** the rolling lookahead band.

    Inactive IDs in ``(last_working_id, last_working_id + LOOKAHEAD_ADS]`` are counted toward
    the stop streak immediately (no row here). Rows are only used for IDs **beyond** that
    band, where ``AD_TIMEOUT_SECONDS`` must elapse before an inactive id counts as dead.
    """

    __tablename__ = "bolha_inactive_ads"

    ad_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    first_inactive_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
