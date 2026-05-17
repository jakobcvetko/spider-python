from datetime import datetime

from pydantic import BaseModel


class TelegramStatusOut(BaseModel):
    connected: bool
    username: str | None = None
    linked_at: datetime | None = None
    notifications_enabled: bool = True


class TelegramLinkOut(BaseModel):
    deep_link_url: str
    expires_at: datetime
