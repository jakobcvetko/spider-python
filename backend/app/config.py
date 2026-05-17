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
    avtonet_lookahead_start_id: int = Field(
        default=22_421_224,
        alias="AVTONET_LOOKAHEAD_START_ID",
    )
    avtonet_lookahead_batch_size: int = Field(
        default=20,
        alias="AVTONET_LOOKAHEAD_BATCH_SIZE",
    )
    avtonet_probe_delay_seconds: float = Field(
        default=0.0,
        alias="AVTONET_PROBE_DELAY_SECONDS",
    )
    avtonet_lookahead_idle_seconds: float = Field(
        default=5.0,
        alias="AVTONET_LOOKAHEAD_IDLE_SECONDS",
    )
    scraperapi_api_key: str | None = Field(default=None, alias="SCRAPERAPI_API_KEY")
    scraperapi_premium: bool = Field(default=False, alias="SCRAPERAPI_PREMIUM")
    scraperapi_render: bool = Field(default=False, alias="SCRAPERAPI_RENDER")
    scraperapi_country_code: str | None = Field(
        default=None,
        alias="SCRAPERAPI_COUNTRY_CODE",
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

    @property
    def scraperapi_enabled(self) -> bool:
        return bool(self.scraperapi_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
