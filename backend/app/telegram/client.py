from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

_API_BASE = "https://api.telegram.org"


class TelegramClient:
    def __init__(self, token: str) -> None:
        self._token = token
        self._base = f"{_API_BASE}/bot{token}"

    async def _post(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{self._base}/{method}", json=payload)
            resp.raise_for_status()
            data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram API {method} failed: {data!r}")
        return data["result"]

    async def get_me(self) -> dict[str, Any]:
        return await self._post("getMe", {})

    async def send_message(
        self,
        chat_id: int,
        text: str,
        *,
        parse_mode: str = "HTML",
        disable_web_page_preview: bool = False,
    ) -> dict[str, Any]:
        return await self._post(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": disable_web_page_preview,
            },
        )

    async def set_webhook(self, url: str, secret_token: str) -> bool:
        result = await self._post(
            "setWebhook",
            {"url": url, "secret_token": secret_token, "allowed_updates": ["message"]},
        )
        return bool(result)

    async def delete_webhook(self) -> bool:
        result = await self._post("deleteWebhook", {"drop_pending_updates": False})
        return bool(result)

    async def get_updates(
        self,
        offset: int | None = None,
        timeout: int = 30,
    ) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {
            "timeout": timeout,
            "allowed_updates": ["message"],
        }
        if offset is not None:
            payload["offset"] = offset
        return await self._post("getUpdates", payload)


def get_telegram_client() -> TelegramClient | None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        return None
    return TelegramClient(settings.telegram_bot_token)
