import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ListingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    external_id: str
    url: str
    title: str
    price_cents: int | None
    currency: str | None
    location: str | None
    image_url: str | None
    year: int | None
    mileage_km: int | None
    created_at: datetime
