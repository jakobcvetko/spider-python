from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.telegram.client import get_telegram_client
from app.telegram.link import LinkTokenFailure, consume_link_token

log = logging.getLogger(__name__)


def _message_text(update: dict[str, Any]) -> str | None:
    message = update.get("message")
    if not isinstance(message, dict):
        return None
    text = message.get("text")
    return text if isinstance(text, str) else None


def _chat_info(update: dict[str, Any]) -> tuple[int, str | None] | None:
    message = update.get("message")
    if not isinstance(message, dict):
        return None
    chat = message.get("chat")
    if not isinstance(chat, dict):
        return None
    chat_id = chat.get("id")
    if not isinstance(chat_id, int):
        return None
    username = chat.get("username")
    return chat_id, username if isinstance(username, str) else None


async def _reply(chat_id: int, text: str) -> None:
    client = get_telegram_client()
    if client is None:
        return
    try:
        await client.send_message(chat_id, text)
    except Exception:
        log.exception("telegram: failed to reply to chat %s", chat_id)


async def handle_update(db: AsyncSession, update: dict[str, Any]) -> None:
    text = _message_text(update)
    chat_info = _chat_info(update)
    if text is None or chat_info is None:
        return

    chat_id, username = chat_info

    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            await _reply(
                chat_id,
                "Open Spider in your browser and tap Connect Telegram to get a link.",
            )
            return

        token = parts[1].strip()
        result = await consume_link_token(db, token, chat_id, username)
        if result is LinkTokenFailure.CHAT_ALREADY_LINKED:
            await _reply(
                chat_id,
                "This Telegram is already connected to another Spider account. "
                "Disconnect it there first, or sign in to that account.",
            )
            return
        if result is LinkTokenFailure.INVALID_OR_EXPIRED:
            await _reply(
                chat_id,
                "This link is invalid or expired. Go back to Spider and tap Connect again.",
            )
            return

        await db.commit()
        await _reply(
            chat_id,
            "<b>Connected to Spider</b>\nYou will receive alerts when new listings match your scrapers.",
        )
        return

    if text.strip() == "/stop":
        from sqlalchemy import select

        result = await db.execute(select(User).where(User.telegram_chat_id == chat_id))
        user = result.scalar_one_or_none()
        if user is None:
            await _reply(chat_id, "This chat is not linked to Spider.")
            return
        user.telegram_notifications_enabled = False
        await db.commit()
        await _reply(
            chat_id,
            "Notifications paused. Reconnect from Spider to enable them again.",
        )
