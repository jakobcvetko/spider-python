from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas.telegram import TelegramLinkOut, TelegramStatusOut
from app.telegram.bot_state import get_bot_username
from app.telegram.link import create_link_token, deep_link_url, disconnect_user
from app.telegram.admin_notify import notify_user_removed_telegram
from app.telegram.notify import send_test_message
from app.telegram.webhook import handle_update

log = logging.getLogger(__name__)
router = APIRouter(prefix="/telegram", tags=["telegram"])


def _require_telegram_configured() -> None:
    if not get_settings().telegram_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram is not configured on this server",
        )


def _status_for_user(user: User) -> TelegramStatusOut:
    return TelegramStatusOut(
        connected=user.telegram_chat_id is not None,
        username=user.telegram_username,
        linked_at=user.telegram_linked_at,
        notifications_enabled=user.telegram_notifications_enabled,
    )


@router.get("/status", response_model=TelegramStatusOut)
async def telegram_status(user: User = Depends(get_current_user)) -> TelegramStatusOut:
    return _status_for_user(user)


@router.post("/link", response_model=TelegramLinkOut)
async def telegram_link(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TelegramLinkOut:
    _require_telegram_configured()
    if get_bot_username() is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram bot is not ready yet; try again in a moment",
        )

    token, expires_at = await create_link_token(db, user)
    await db.commit()

    url = deep_link_url(token)
    if url is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram bot is not ready yet; try again in a moment",
        )

    return TelegramLinkOut(deep_link_url=url, expires_at=expires_at)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def telegram_disconnect(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    await notify_user_removed_telegram(db, user)
    await disconnect_user(db, user)
    await db.commit()


@router.post("/test", status_code=status.HTTP_204_NO_CONTENT)
async def telegram_test(user: User = Depends(get_current_user)) -> None:
    _require_telegram_configured()
    if user.telegram_chat_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram is not connected",
        )
    try:
        await send_test_message(user.telegram_chat_id)
    except Exception as e:
        log.exception("telegram: test message failed for user %s", user.id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to send Telegram message",
        ) from e


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    settings = get_settings()
    if not settings.telegram_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    expected = settings.telegram_webhook_secret
    if expected and x_telegram_bot_api_secret_token != expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    body: dict[str, Any] = await request.json()
    try:
        await handle_update(db, body)
    except Exception:
        await db.rollback()
        log.exception("telegram: webhook handler failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return {"ok": True}
