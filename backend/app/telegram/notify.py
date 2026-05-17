from __future__ import annotations

import html
import logging
import uuid
from dataclasses import dataclass

from app.models import Listing
from app.telegram.client import get_telegram_client

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class NewMatch:
    user_id: uuid.UUID
    scraper_name: str
    listing: Listing
    telegram_chat_id: int


def _format_price(listing: Listing) -> str | None:
    if listing.price_cents is not None and listing.currency:
        amount = listing.price_cents / 100
        return f"{amount:,.0f} {listing.currency}".replace(",", ".")
    if listing.price_decimal is not None:
        return f"{listing.price_decimal:,.0f}".replace(",", ".")
    return None


def format_match_message(listing: Listing, scraper_name: str) -> str:
    title = html.escape(listing.title)
    scraper = html.escape(scraper_name)
    source = html.escape(listing.source)
    parts = [f"<b>New match</b> — {scraper}", "", title]

    price = _format_price(listing)
    if price:
        parts.append(html.escape(price))
    if listing.location:
        parts.append(html.escape(listing.location))
    parts.append(f"Source: {source}")
    parts.append(f'<a href="{html.escape(listing.url, quote=True)}">View listing</a>')
    return "\n".join(parts)


async def notify_new_matches(matches: list[NewMatch]) -> None:
    client = get_telegram_client()
    if client is None or not matches:
        return

    for match in matches:
        text = format_match_message(match.listing, match.scraper_name)
        try:
            await client.send_message(match.telegram_chat_id, text)
        except Exception:
            log.exception(
                "telegram: failed to notify user %s for listing %s",
                match.user_id,
                match.listing.id,
            )


async def send_test_message(chat_id: int) -> None:
    client = get_telegram_client()
    if client is None:
        raise RuntimeError("Telegram is not configured")
    await client.send_message(
        chat_id,
        "<b>Spider</b> is connected. You will receive alerts when new listings match your scrapers.",
    )
