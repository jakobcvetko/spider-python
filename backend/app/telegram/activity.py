from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TelegramLinkToken, User, UserActivity

TELEGRAM_START = "telegram_start"
TELEGRAM_STOP = "telegram_stop"
TELEGRAM_MESSAGE = "telegram_message"


async def user_id_for_chat(db: AsyncSession, chat_id: int) -> uuid.UUID | None:
    result = await db.execute(select(User.id).where(User.telegram_chat_id == chat_id))
    return result.scalar_one_or_none()


async def user_id_for_link_token(db: AsyncSession, token: str) -> uuid.UUID | None:
    result = await db.execute(
        select(TelegramLinkToken.user_id).where(TelegramLinkToken.token == token)
    )
    return result.scalar_one_or_none()


def redact_start_body(text: str) -> str:
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return "/start"
    return "/start …"


async def record_telegram_activity(
    db: AsyncSession,
    *,
    kind: str,
    telegram_chat_id: int,
    user_id: uuid.UUID | None = None,
    body: str | None = None,
    detail: str | None = None,
) -> None:
    if user_id is None:
        user_id = await user_id_for_chat(db, telegram_chat_id)

    db.add(
        UserActivity(
            user_id=user_id,
            telegram_chat_id=telegram_chat_id,
            kind=kind,
            body=body,
            detail=detail,
        )
    )
    await db.flush()
