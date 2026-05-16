from scraper.sources.avto_net import AvtoNetSource
from scraper.sources.bolha_backfill import BolhaBackfillSource
from scraper.sources.bolha_lookahead import BolhaLookaheadSource

ALL_SOURCES = [
    AvtoNetSource(),
    BolhaBackfillSource(),
    BolhaLookaheadSource(),
]

__all__ = [
    "AvtoNetSource",
    "BolhaLookaheadSource",
    "BolhaBackfillSource",
    "ALL_SOURCES",
]
