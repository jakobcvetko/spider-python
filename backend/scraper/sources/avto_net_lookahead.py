"""avto.net ID lookahead — fixed 20-ID band ahead of last_working (mirrors bolha.lookahead)."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone
from typing import NoReturn

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import SessionLocal
from app.matcher_jobs import enqueue_matcher_job
from scraper.base import get_listing_id, upsert_items
from scraper.sources.avto_net_common import LISTING_SOURCE, LOOKAHEAD_ADS
from scraper.sources.avto_net_scout import run_avtonet_scout
from scraper.sources.avtonet_pipeline import (
    EmitFn,
    LOOKAHEAD_HIGH_WATER_REFRESH_BATCHES,
    LOOKAHEAD_TIMEOUT_SECONDS,
    delete_ad_state,
    delete_lookahead_below_ad,
    emit_progress_tick,
    get_meta,
    max_numeric_listing_id,
    meta_begin_fetch,
    meta_set_last_working,
    outcome_from_class,
    pipeline_kind_from_probe,
    promote_lookahead_below_to_pending_fallback,
    record_avtonet_ad_scrape_from_outcome,
    upsert_expired_state,
    upsert_lookahead_state,
    upsert_probe,
)
from scraper.sources.avto_net_probe import probe_ad_id as fetch_probe

log = logging.getLogger(__name__)

SOURCE_NAME = "avto.net.lookahead"


class AvtoNetLookaheadSource:
    name = SOURCE_NAME
    listing_source = LISTING_SOURCE

    def __init__(self) -> None:
        self._batch_count = 0
        self._cached_db_max: int | None = None

    async def _refresh_high_water(
        self,
        db: AsyncSession,
        *,
        meta_anchor: int,
    ) -> int:
        self._batch_count += 1
        refresh_db = (
            self._cached_db_max is None
            or self._batch_count % LOOKAHEAD_HIGH_WATER_REFRESH_BATCHES == 0
            or meta_anchor >= (self._cached_db_max or 0)
        )
        if refresh_db:
            self._cached_db_max = await max_numeric_listing_id(db)
        return max(meta_anchor, self._cached_db_max or 0)

    async def fetch(
        self,
        client: httpx.AsyncClient,
        emit: EmitFn = None,
    ) -> NoReturn:
        settings = get_settings()
        try:
            async with SessionLocal() as db:
                log.info("avto.net lookahead: running initial scout")
                try:
                    await run_avtonet_scout(db, client, emit)
                except RuntimeError:
                    log.exception(
                        "avto.net lookahead: initial scout failed; "
                        "continuing with stored anchor"
                    )

                while True:
                    meta = await get_meta(db)
                    anchor = int(meta.last_working_ad_id or 0)
                    high = await self._refresh_high_water(db, meta_anchor=anchor)

                    await meta_begin_fetch(db, high=high)
                    log.info(
                        "avto.net lookahead: batch anchor=%s high_water=%s",
                        anchor,
                        high,
                    )

                    batch_resolved = False
                    for k in range(1, LOOKAHEAD_ADS + 1):
                        ad_id = anchor + k
                        now = datetime.now(timezone.utc)
                        try:
                            result = await fetch_probe(
                                client,
                                ad_id,
                                settings=settings,
                                emit=emit,
                                source=self.name,
                            )
                        except httpx.HTTPError as e:
                            log.warning(
                                "avto.net lookahead: probe %s failed: %s", ad_id, e
                            )
                            await upsert_probe(
                                db,
                                ad_id,
                                fetched_at=now,
                                http_status=-1,
                                outcome="http_error",
                                detail=str(e)[:500],
                            )
                            await record_avtonet_ad_scrape_from_outcome(
                                db,
                                ad_id,
                                source=self.name,
                                outcome="http_error",
                                fetched_at=now,
                                http_status=-1,
                                detail=str(e),
                                emit=emit,
                            )
                            await upsert_lookahead_state(
                                db,
                                ad_id,
                                now=now,
                                last_outcome="http_error",
                                detail=str(e)[:500],
                            )
                            await emit_progress_tick(
                                emit,
                                scraper_name=self.name,
                                ad_id=ad_id,
                                last_working_ad_id=anchor,
                                high_water=high,
                                outcome="http_error",
                                http_status=-1,
                            )
                            continue

                        kind = pipeline_kind_from_probe(result)
                        oc = outcome_from_class(kind)

                        await upsert_probe(
                            db,
                            ad_id,
                            fetched_at=now,
                            http_status=result.http_status,
                            outcome=oc,
                            detail=result.detail,
                        )
                        await record_avtonet_ad_scrape_from_outcome(
                            db,
                            ad_id,
                            source=self.name,
                            outcome=oc,
                            fetched_at=now,
                            http_status=result.http_status,
                            detail=result.detail,
                            emit=emit,
                        )

                        if kind == "active" and result.item is not None:
                            await emit_progress_tick(
                                emit,
                                scraper_name=self.name,
                                ad_id=ad_id,
                                last_working_ad_id=anchor,
                                high_water=high,
                                outcome=oc,
                                http_status=result.http_status,
                            )
                            await promote_lookahead_below_to_pending_fallback(
                                db, ad_id, now=now
                            )
                            await delete_ad_state(db, ad_id)
                            await meta_set_last_working(db, ad_id)
                            try:
                                inserted = await upsert_items(
                                    db, LISTING_SOURCE, [result.item]
                                )
                            except Exception:
                                log.exception(
                                    "avto.net lookahead: upsert failed for ad_id=%s",
                                    ad_id,
                                )
                                inserted = 0

                            listing_id = await get_listing_id(
                                db, LISTING_SOURCE, str(ad_id)
                            )
                            if listing_id is not None:
                                try:
                                    await enqueue_matcher_job(db, listing_id)
                                except Exception:
                                    log.exception(
                                        "avto.net lookahead: matcher enqueue failed ad_id=%s",
                                        ad_id,
                                    )

                            self._cached_db_max = max(
                                self._cached_db_max or 0, ad_id
                            )
                            log.info(
                                "avto.net lookahead: active ad_id=%s (anchor was %s), inserted=%s",
                                ad_id,
                                anchor,
                                inserted,
                            )
                            batch_resolved = True
                            await db.commit()
                            break

                        if kind == "expired":
                            await emit_progress_tick(
                                emit,
                                scraper_name=self.name,
                                ad_id=ad_id,
                                last_working_ad_id=ad_id,
                                high_water=high,
                                outcome=oc,
                                http_status=result.http_status,
                            )
                            await upsert_expired_state(
                                db, ad_id, now=now, last_outcome=oc, detail=result.detail
                            )
                            await delete_lookahead_below_ad(db, ad_id)
                            await meta_set_last_working(db, ad_id)
                            await db.commit()
                            log.info(
                                "avto.net lookahead: expired ad_id=%s (anchor was %s), "
                                "advanced last_working, no backfill",
                                ad_id,
                                anchor,
                            )
                            batch_resolved = True
                            break

                        await upsert_lookahead_state(
                            db,
                            ad_id,
                            now=now,
                            last_outcome=oc,
                            detail=result.detail,
                        )
                        await emit_progress_tick(
                            emit,
                            scraper_name=self.name,
                            ad_id=ad_id,
                            last_working_ad_id=anchor,
                            high_water=high,
                            outcome=oc,
                            http_status=result.http_status,
                        )

                    if not batch_resolved:
                        await db.commit()
                        await asyncio.sleep(LOOKAHEAD_TIMEOUT_SECONDS)
        finally:
            pass


async def _run_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Probe avto.net detail URLs (Bolha-style lookahead band).",
    )
    parser.add_argument("--start-id", type=int, default=None)
    parser.add_argument("--count", type=int, default=LOOKAHEAD_ADS)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="HTTP-only smoke test (no DB writes)",
    )
    args = parser.parse_args(argv)
    settings = get_settings()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    headers = {
        "User-Agent": settings.scraper_user_agent,
        "Accept-Language": "sl,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml",
    }

    async with httpx.AsyncClient(
        headers=headers,
        follow_redirects=True,
        timeout=httpx.Timeout(30.0),
    ) as client:
        source = AvtoNetLookaheadSource()
        if args.loop:
            await source.fetch(client)
            return 0
        log.warning("Single-batch CLI removed; use --loop or make avtonet:lookahead")
        return 1


def main(argv: list[str] | None = None) -> None:
    raise SystemExit(asyncio.run(_run_cli(argv if argv is not None else sys.argv[1:])))


if __name__ == "__main__":
    main()
