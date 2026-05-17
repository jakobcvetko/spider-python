from __future__ import annotations

import enum
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import TelegramLinkToken, User
from app.telegram.bot_state import get_bot_username


class LinkTokenFailure(enum.StrEnum):
    INVALID_OR_EXPIRED = "invalid_or_expired"
    CHAT_ALREADY_LINKED = "chat_already_linked"


def deep_link_url(token: str) -> str | None:
    username = get_bot_username()
    if not username:
        return None
    return f"https://t.me/{username}?start={token}"


async def create_link_token(db: AsyncSession, user: User) -> tuple[str, datetime]:
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.telegram_link_token_ttl_minutes)
    token = secrets.token_urlsafe(24)

    await db.execute(delete(TelegramLinkToken).where(TelegramLinkToken.user_id == user.id))

    row = TelegramLinkToken(
        user_id=user.id,
        token=token,
        expires_at=expires_at,
        created_at=datetime.now(UTC),
    )
    db.add(row)
    await db.flush()
    return token, expires_at


async def consume_link_token(
    db: AsyncSession,
    token: str,
    chat_id: int,
    username: str | None,
) -> User | LinkTokenFailure:
    now = datetime.now(UTC)
    result = await db.execute(
        select(TelegramLinkToken).where(TelegramLinkToken.token == token)
    )
    link = result.scalar_one_or_none()
    if link is None or link.expires_at < now:
        return LinkTokenFailure.INVALID_OR_EXPIRED

    user = await db.get(User, link.user_id)
    if user is None:
        return LinkTokenFailure.INVALID_OR_EXPIRED

    existing = await db.execute(
        select(User).where(
            User.telegram_chat_id == chat_id,
            User.id != user.id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        return LinkTokenFailure.CHAT_ALREADY_LINKED

    user.telegram_chat_id = chat_id
    user.telegram_username = username
    user.telegram_linked_at = now
    user.telegram_notifications_enabled = True

    await db.execute(delete(TelegramLinkToken).where(TelegramLinkToken.user_id == user.id))
    await db.flush()
    return user


async def disconnect_user(db: AsyncSession, user: User) -> None:
    user.telegram_chat_id = None
    user.telegram_username = None
    user.telegram_linked_at = None
    user.telegram_notifications_enabled = True
    await db.execute(delete(TelegramLinkToken).where(TelegramLinkToken.user_id == user.id))
    await db.flush()
