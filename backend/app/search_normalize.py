"""Normalize listing/scraper text for token-based substring matching."""

from __future__ import annotations

import re
import unicodedata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.scraper import Scraper

MIN_SCRAPER_TOKEN_LEN = 2

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Casefold, strip diacritics, collapse whitespace."""
    folded = text.casefold()
    decomposed = unicodedata.normalize("NFKD", folded)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return _WHITESPACE_RE.sub(" ", stripped).strip()


def tokenize_scraper_name(name: str) -> list[str]:
    """Split scraper name into deduped search tokens (min length enforced)."""
    normalized = normalize_text(name.strip())
    if not normalized:
        return []
    seen: set[str] = set()
    tokens: list[str] = []
    for part in normalized.split():
        if len(part) < MIN_SCRAPER_TOKEN_LEN:
            continue
        if part in seen:
            continue
        seen.add(part)
        tokens.append(part)
    return tokens


def title_matches_scraper_tokens(normalized_title: str, tokens: list[str]) -> bool:
    """True when every scraper token is a substring of the normalized listing title."""
    if not tokens:
        return False
    return all(token in normalized_title for token in tokens)


def sync_scraper_search_tokens(scraper: Scraper) -> None:
    """Update ``scraper.search_tokens`` from ``scraper.name``."""
    scraper.search_tokens = tokenize_scraper_name(scraper.name)
