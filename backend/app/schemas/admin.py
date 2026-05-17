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
    activity_count: int = 0
    telegram_connected: bool = False
    telegram_username: str | None = None


class UserActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    telegram_chat_id: int | None
    kind: str
    body: str | None
    detail: str | None
    created_at: datetime


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


class AdminListingOut(BaseModel):
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
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime
    matches_count: int = 0


class AdminListingMatchOut(BaseModel):
    scraper_id: uuid.UUID
    scraper_name: str
    user_email: EmailStr
    bolha_enabled: bool
    avtonet_enabled: bool
    matched_at: datetime


class BolhaProgressiveRow(BaseModel):
    ad_id: int
    zone: str
    display_status: str
    outcome: str | None
    http_status: int | None
    gtm_ad_status: str | None
    fetched_at: datetime | None
    inactive_age_seconds: float | None
    detail: str | None
    pipeline_status: str | None = None


class BolhaProgressiveState(BaseModel):
    look_ahead_count: int
    last_working_ad_id: int
    last_working_at: datetime | None
    scan_anchor_ad_id: int
    last_homepage_max: int
    last_fetch_high_water: int
    last_fetch_started_at: datetime | None
    db_numeric_max: int
    lookahead_rows: list[BolhaProgressiveRow]
    pivot_row: BolhaProgressiveRow
    tail_rows: list[BolhaProgressiveRow]


class BolhaAdScrapeEntryOut(BaseModel):
    offset_seconds: float
    at: datetime
    source: str
    result: str
    http_status: int | None = None
    detail: str | None = None


class BolhaAdOut(BaseModel):
    ad_id: int
    status: str
    created_at: datetime
    updated_at: datetime
    scrapes: list[BolhaAdScrapeEntryOut]
    listing_published_at: datetime | None = None
    listing_created_at: datetime | None = None


class BolhaAdMatchResponse(BaseModel):
    ad_id: int
    listing_id: uuid.UUID
    matches_created: int


class AvtonetAdScrapeEntryOut(BaseModel):
    offset_seconds: float
    at: datetime
    source: str
    result: str
    http_status: int | None = None
    detail: str | None = None


class AvtonetAdOut(BaseModel):
    ad_id: int
    status: str
    created_at: datetime
    updated_at: datetime
    scrapes: list[AvtonetAdScrapeEntryOut]
    listing_published_at: datetime | None = None
    listing_created_at: datetime | None = None


class AvtonetAdMatchResponse(BaseModel):
    ad_id: int
    listing_id: uuid.UUID
    matches_created: int


class AvtonetScrapeState(BaseModel):
    last_working_ad_id: int
    last_working_at: datetime | None
    last_batch_started_at: datetime | None
    lookahead_batch_size: int
    probe_delay_seconds: float
    fetch_mode: str
    scraperapi_enabled: bool


class BolhaAdStateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ad_id: int
    status: str
    last_lookahead_at: datetime | None
    first_fallback_scrape_at: datetime | None
    last_fallback_scrape_at: datetime | None
    last_outcome: str | None
    last_detail: str | None
    created_at: datetime
    updated_at: datetime
