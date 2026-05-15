from __future__ import annotations

import logging
import re
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser

from scraper.base import ScrapedItem

log = logging.getLogger(__name__)

# Default search: latest cars (newest first). Tune the query string for your needs.
SEARCH_URL = (
    "https://www.avto.net/Ads/results.asp?"
    "znamka=&model=&modelID=&tip=&znamka2=&model2=&tip2="
    "&znamka3=&model3=&tip3=&cenaMin=0&cenaMax=999999"
    "&letnikMin=0&letnikMax=2090&bencin=0&starost2=99"
    "&oblika=0&ccmMin=0&ccmMax=99000&mocMin=0&mocMax=999"
    "&kmMin=0&kmMax=9999999&kwMin=0&kwMax=999&motortakt=0"
    "&motorvalji=0&lokacija=0&sirina=0&dolzina=0&dolzinaMIN=0"
    "&dolzinaMAX=100&nosilnostMIN=0&nosilnostMAX=999"
    "&lezisc=0&presek=0&premer=0&col=0&vijakov=0&EToznaka="
    "&vozilo=&airbag=&barva=&barvaint=&Q=&PIA=False&PIAzero=False"
    "&PIAOpombe=False&PSLO=False&akcija=0&paketgarancije=0"
    "&apaket=&apaketID=0&garancija=0&zaloga=10"
    "&prikaz=10&stran=1"
)

PRICE_RE = re.compile(r"(\d[\d\.\s]*),?(\d{0,2})")
ID_RE = re.compile(r"id=(\d+)|/(\d+)/?$|oglas[^\d]*(\d+)", re.IGNORECASE)


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


def _parse_int(text: str | None) -> int | None:
    if not text:
        return None
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else None


class AvtoNetSource:
    name = "avto.net"

    async def fetch(self, client: httpx.AsyncClient) -> list[ScrapedItem]:
        try:
            resp = await client.get(SEARCH_URL, timeout=20.0)
        except httpx.HTTPError as e:
            log.warning("avto.net request failed: %s", e)
            return []

        if resp.status_code != 200:
            log.warning("avto.net returned status %s", resp.status_code)
            return []

        return _parse_results(resp.text)


def _parse_results(html: str) -> list[ScrapedItem]:
    """Best-effort parser. avto.net's HTML structure changes; refine selectors as needed."""
    tree = HTMLParser(html)
    items: list[ScrapedItem] = []
    seen_ids: set[str] = set()

    # Each ad is generally inside an <a> linking to /Ads/details.asp?id=NNN
    for a in tree.css("a[href*='details.asp']"):
        href = a.attributes.get("href") or ""
        m = ID_RE.search(href)
        ext_id = next((g for g in m.groups() if g), None) if m else None
        if not ext_id or ext_id in seen_ids:
            continue
        seen_ids.add(ext_id)

        absolute_url = urljoin("https://www.avto.net/", href)
        # Pull text content as title fallback
        title = (a.text(strip=True) or "").strip()
        if not title:
            title_node = a.css_first("h2, h3, .title, strong")
            title = title_node.text(strip=True) if title_node else "Unknown listing"

        # Try to find a sibling/ancestor card to extract price/location
        card = a
        for _ in range(4):
            if card.parent is None:
                break
            card = card.parent

        price_text = None
        location = None
        image_url = None
        year = None
        mileage_km = None

        if card is not None:
            for el in card.css("*"):
                txt = (el.text(strip=True) or "")
                if not txt:
                    continue
                low = txt.lower()
                if price_text is None and ("€" in txt or "eur" in low):
                    price_text = txt
                if year is None and re.search(r"\b(19|20)\d{2}\b", txt):
                    yr = re.search(r"\b(19|20)\d{2}\b", txt)
                    if yr:
                        year = int(yr.group(0))
                if mileage_km is None and ("km" in low):
                    mileage_km = _parse_int(txt)
                if location is None and ("lokacija" in low or "kraj" in low):
                    location = txt

            img = card.css_first("img")
            if img is not None:
                image_url = img.attributes.get("src") or img.attributes.get("data-src")
                if image_url:
                    image_url = urljoin("https://www.avto.net/", image_url)

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
                year=year,
                mileage_km=mileage_km,
                raw={"source_html_snippet": title},
            )
        )

    return items
