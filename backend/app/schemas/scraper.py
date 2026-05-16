import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScraperOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    bolha_enabled: bool
    avtonet_enabled: bool
    created_at: datetime
    updated_at: datetime


class ScraperCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    bolha_enabled: bool = False
    avtonet_enabled: bool = False

    @model_validator(mode="after")
    def validate_sources(self) -> "ScraperCreateIn":
        if self.avtonet_enabled:
            raise ValueError("Avto.net is not available yet")
        if not self.bolha_enabled:
            raise ValueError("Select at least one source")
        return self


class ScraperUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    bolha_enabled: bool | None = None
    avtonet_enabled: bool | None = None

    @model_validator(mode="after")
    def reject_avtonet(self) -> "ScraperUpdateIn":
        if self.avtonet_enabled is True:
            raise ValueError("Avto.net is not available yet")
        return self
