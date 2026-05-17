from __future__ import annotations

import html
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Scraper, User
from app.telegram.client import get_telegram_client

log = logging.getLogger(__name__)

_MAX_MESSAGE_BODY = 300


def _escape(text: str) -> str:
    return html.escape(text, quote=False)


def _user_label(user: User) -> str:
    label = user.email
    if user.display_name:
        label = f"{user.display_name} ({user.email})"
    return _escape(label)


def _truncate(text: str, max_len: int = _MAX_MESSAGE_BODY) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _sources_label(scraper: Scraper) -> str:
    parts: list[str] = []
    if scraper.bolha_enabled:
        parts.append("Bolha")
    if scraper.avtonet_enabled:
        parts.append("Avto.net")
    return ", ".join(parts) if parts else "—"


async def _admin_chat_ids(db: AsyncSession) -> list[int]:
    result = await db.execute(
        select(User.telegram_chat_id).where(
            User.is_admin.is_(True),
            User.telegram_chat_id.isnot(None),
        )
    )
    return [cid for cid in result.scalars().all() if cid is not None]


async def notify_admins(db: AsyncSession, text: str) -> None:
    client = get_telegram_client()
    if client is None:
        return
    chat_ids = await _admin_chat_ids(db)
    if not chat_ids:
        return
    for chat_id in chat_ids:
        try:
            await client.send_message(chat_id, text)
        except Exception:
            log.exception("telegram: failed admin notify to chat %s", chat_id)


async def notify_user_registered(db: AsyncSession, user: User) -> None:
    await notify_admins(
        db,
        f"<b>Nov uporabnik</b>\n{_user_label(user)}",
    )


async def notify_user_linked_telegram(db: AsyncSession, user: User) -> None:
    handle = f"@{_escape(user.telegram_username)}" if user.telegram_username else "—"
    await notify_admins(
        db,
        f"<b>Telegram povezan</b>\n{_user_label(user)}\n{handle}",
    )


async def notify_user_telegram_message(
    db: AsyncSession,
    *,
    user: User | None,
    chat_id: int,
    body: str,
) -> None:
    who = _user_label(user) if user is not None else _escape(f"chat {chat_id}")
    preview = _escape(_truncate(body.strip()))
    await notify_admins(
        db,
        f"<b>Sporočilo prek Telegrama</b>\n{who}\n\n{preview}",
    )


async def notify_user_stopped_telegram(db: AsyncSession, user: User) -> None:
    await notify_admins(
        db,
        f"<b>Prejemanje ustavljeno</b>\n{_user_label(user)} je poslal /stop",
    )


async def notify_user_removed_telegram(db: AsyncSession, user: User) -> None:
    await notify_admins(
        db,
        f"<b>Telegram odstranjen</b>\n{_user_label(user)}",
    )


async def notify_scraper_created(db: AsyncSession, user: User, scraper: Scraper) -> None:
    name = _escape(scraper.name)
    sources = _escape(_sources_label(scraper))
    await notify_admins(
        db,
        f"<b>Nov scraper</b>\n{_user_label(user)}\n«{name}» ({sources})",
    )


async def notify_scraper_updated(db: AsyncSession, user: User, scraper: Scraper) -> None:
    name = _escape(scraper.name)
    sources = _escape(_sources_label(scraper))
    await notify_admins(
        db,
        f"<b>Scraper urejen</b>\n{_user_label(user)}\n«{name}» ({sources})",
    )


async def notify_scraper_deleted(
    db: AsyncSession,
    user: User,
    *,
    scraper_id: uuid.UUID,
    name: str,
) -> None:
    await notify_admins(
        db,
        f"<b>Scraper izbrisan</b>\n{_user_label(user)}\n«{_escape(name)}»",
    )
