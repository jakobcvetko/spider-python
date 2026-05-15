from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser

from scraper.base import ScrapedItem

log = logging.getLogger(__name__)

# Default: newest ads in the cars top-level category. Adjust to your category.
SEARCH_URL = "https://www.bolha.com/avtomobili"

ID_RE = re.compile(r"-(\d+)(?:\.html|/?$)")


def _parse_price_cents(text: str | None) -> tuple[int | None, str | None]:
    if not text:
        return None, None
    cur = "EUR" if "€" in text or "EUR" in text.upper() else None
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return None, cur
    try:
        return int(digits) * 100, cur
    except ValueError:
        return None, cur


class BolhaSource:
    name = "bolha.com"

    async def fetch(self, client: httpx.AsyncClient) -> list[ScrapedItem]:
        try:
            resp = await client.get(SEARCH_URL, timeout=20.0)
        except httpx.HTTPError as e:
            log.warning("bolha.com request failed: %s", e)
            return []

        if resp.status_code != 200:
            log.warning("bolha.com returned status %s", resp.status_code)
            return []

        return _parse_results(resp.text)


def _parse_results(html: str) -> list[ScrapedItem]:
    tree = HTMLParser(html)
    items: list[ScrapedItem] = []
    seen_ids: set[str] = set()

    # bolha.com listings are typically <article> or <li> entries containing a link to the ad detail page.
    for a in tree.css("a[href*='/oglas/'], a[href*='/avtomobili/'][href$='.html']"):
        href = a.attributes.get("href") or ""
        m = ID_RE.search(href)
        ext_id = m.group(1) if m else None
        if not ext_id or ext_id in seen_ids:
            continue
        seen_ids.add(ext_id)

        absolute_url = urljoin("https://www.bolha.com/", href)
        title = (a.text(strip=True) or "").strip() or "Unknown listing"

        card = a
        for _ in range(4):
            if card.parent is None:
                break
            card = card.parent

        price_text = None
        location = None
        image_url = None

        if card is not None:
            price_node = card.css_first("[class*=price], .price, strong:contains('€')")
            if price_node is not None:
                price_text = price_node.text(strip=True)
            else:
                for el in card.css("*"):
                    txt = el.text(strip=True) or ""
                    if "€" in txt or "EUR" in txt.upper():
                        price_text = txt
                        break

            loc_node = card.css_first("[class*=location], [class*=lokacija]")
            if loc_node is not None:
                location = loc_node.text(strip=True)

            img = card.css_first("img")
            if img is not None:
                image_url = img.attributes.get("src") or img.attributes.get("data-src")
                if image_url:
                    image_url = urljoin("https://www.bolha.com/", image_url)

        price_cents, currency = _parse_price_cents(price_text)

        items.append(
            ScrapedItem(
                external_id=ext_id,
                url=absolute_url,
                title=title[:500],
                price_cents=price_cents,
                currency=currency,
                location=location,
                image_url=image_url,
                raw={"source_href": href},
            )
        )

    return items
