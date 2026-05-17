from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://spider:spider@localhost:5432/spider",
        alias="DATABASE_URL",
    )
    alembic_database_url: str = Field(
        default="postgresql+psycopg://spider:spider@localhost:5432/spider",
        alias="ALEMBIC_DATABASE_URL",
    )
    session_cookie_name: str = Field(default="spider_session", alias="SESSION_COOKIE_NAME")
    session_lifetime_days: int = Field(default=14, alias="SESSION_LIFETIME_DAYS")
    session_cookie_secure: bool = Field(default=False, alias="SESSION_COOKIE_SECURE")
    cors_origins: str = Field(
        default="http://127.0.0.1:3000,http://localhost:3000",
        alias="CORS_ORIGINS",
    )
    scrape_interval_seconds: int = Field(default=60, alias="SCRAPE_INTERVAL_SECONDS")
    scraper_user_agent: str = Field(
        default="spider-bot/0.1 (+https://example.com)",
        alias="SCRAPER_USER_AGENT",
    )
    telegram_bot_token: str | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_webhook_secret: str | None = Field(default=None, alias="TELEGRAM_WEBHOOK_SECRET")
    telegram_webhook_base_url: str | None = Field(
        default=None, alias="TELEGRAM_WEBHOOK_BASE_URL"
    )
    telegram_polling: bool = Field(default=False, alias="TELEGRAM_POLLING")
    telegram_link_token_ttl_minutes: int = Field(
        default=15, alias="TELEGRAM_LINK_TOKEN_TTL_MINUTES"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token)


@lru_cache
def get_settings() -> Settings:
    return Settings()
