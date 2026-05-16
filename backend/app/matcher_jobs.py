"""Postgres NOTIFY queue for the standalone matcher worker."""

from __future__ import annotations

import json
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

MATCHER_JOBS_CHANNEL = "matcher_jobs"


async def enqueue_matcher_job(db: AsyncSession, listing_id: uuid.UUID) -> None:
    """Notify the matcher process; does not commit the session."""
    payload = json.dumps({"listing_id": str(listing_id)})
    await db.execute(
        text("SELECT pg_notify(:channel, :payload)"),
        {"channel": MATCHER_JOBS_CHANNEL, "payload": payload},
    )
