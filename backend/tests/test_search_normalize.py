from __future__ import annotations

from app.search_normalize import (
    normalize_text,
    title_matches_scraper_tokens,
    tokenize_scraper_name,
)


def test_normalize_strips_diacritics() -> None:
    assert normalize_text("Čistilec") == "cistilec"
    assert normalize_text("MUTA") == "muta"


def test_tokenize_scraper_name_dedupes_and_min_length() -> None:
    assert tokenize_scraper_name("MUTA Čistilec") == ["muta", "cistilec"]
    assert tokenize_scraper_name("muta muta x") == ["muta"]


def test_title_matches_scraper_tokens_cases() -> None:
    cases = [
        ("MUTA Čistilec", "Prodam čistilec tipa Muta", True),
        ("MUTA Čistilec", "Muta", False),
        ("cist mut", "Čistilec Muta", True),
        ("MUTA Prikolica", "Prikolica MUTA", True),
        ("MUTA Prikolica", "MUTA-Prikolica", True),
    ]
    for scraper_name, listing_title, expected in cases:
        tokens = tokenize_scraper_name(scraper_name)
        normalized = normalize_text(listing_title)
        assert title_matches_scraper_tokens(normalized, tokens) is expected, (
            scraper_name,
            listing_title,
        )
