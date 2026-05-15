import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    display_name: str | None
    is_admin: bool
    created_at: datetime
    updated_at: datetime


class ScraperStatus(BaseModel):
    connected: bool
    last_heartbeat_ts: float | None
    seconds_since_heartbeat: float | None
    sources: list[str]
    interval_seconds: int
    recent_events: list[dict[str, Any]]


class TriggerResponse(BaseModel):
    queued: bool
    reason: str


class RunSourceBody(BaseModel):
    source: str

    @field_validator("source")
    @classmethod
    def strip_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("source must not be empty")
        return s


class RunSourceResponse(BaseModel):
    queued: bool
    reason: str
    source: str
