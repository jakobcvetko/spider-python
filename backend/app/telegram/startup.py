from __future__ import annotations

import asyncio
import logging

from app.config import get_settings
from app.telegram.bot_state import set_bot_username
from app.telegram.client import get_telegram_client
from app.telegram.polling import run_polling

log = logging.getLogger(__name__)


async def setup_telegram(stop: asyncio.Event) -> asyncio.Task | None:
    settings = get_settings()
    if not settings.telegram_enabled:
        return None

    client = get_telegram_client()
    if client is None:
        return None

    try:
        me = await client.get_me()
        username = me.get("username")
        if isinstance(username, str):
            set_bot_username(username)
            log.info("telegram: bot @%s ready", username)
    except Exception:
        log.exception("telegram: getMe failed")
        return None

    base = (settings.telegram_webhook_base_url or "").rstrip("/")
    secret = settings.telegram_webhook_secret

    if base and secret:
        webhook_url = f"{base}/api/telegram/webhook"
        try:
            await client.set_webhook(webhook_url, secret)
            log.info("telegram: webhook set to %s", webhook_url)
        except Exception:
            log.exception("telegram: setWebhook failed")
    elif settings.telegram_polling:
        return asyncio.create_task(run_polling(stop))
    else:
        log.warning(
            "telegram: no webhook base URL and polling disabled; "
            "bot updates will not be received"
        )

    return None
