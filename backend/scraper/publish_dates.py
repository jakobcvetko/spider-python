"""Extract site-published timestamps from listing detail HTML."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

_LJUBLJANA = ZoneInfo("Europe/Ljubljana")

_BOLHA_PUBLISHED_RE = re.compile(
    r"Oglas je objavljen\s*</dt>\s*<dd[^>]*>\s*"
    r"(\d{1,2})\.(\d{1,2})\.(\d{4})\.?\s*(?:ob\s+(\d{1,2}):(\d{2}))?",
    re.IGNORECASE | re.DOTALL,
)

_AVTONET_PUBLISHED_RE = re.compile(
    r"Zadnja sprememba:\s*(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{1,2}):(\d{2}):(\d{2})",
    re.IGNORECASE,
)


def _local_to_utc(
    day: int,
    month: int,
    year: int,
    *,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
) -> datetime:
    local = datetime(year, month, day, hour, minute, second, tzinfo=_LJUBLJANA)
    return local.astimezone(timezone.utc)


def parse_bolha_published_at(html: str) -> datetime | None:
    m = _BOLHA_PUBLISHED_RE.search(html)
    if not m:
        return None
    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    hour = int(m.group(4)) if m.group(4) else 0
    minute = int(m.group(5)) if m.group(5) else 0
    return _local_to_utc(day, month, year, hour=hour, minute=minute)


def parse_avtonet_published_at(html: str) -> datetime | None:
    """Best-effort from the listing stats line (Zadnja sprememba)."""
    m = _AVTONET_PUBLISHED_RE.search(html)
    if not m:
        return None
    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    hour, minute, second = int(m.group(4)), int(m.group(5)), int(m.group(6))
    return _local_to_utc(day, month, year, hour=hour, minute=minute, second=second)
