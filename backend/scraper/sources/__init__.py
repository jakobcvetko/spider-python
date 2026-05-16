from scraper.sources.avto_net import AvtoNetSource
from scraper.sources.bolha_backfill import BolhaBackfillSource
from scraper.sources.bolha_lookahead import BolhaLookaheadSource
from scraper.sources.bolha_scout import BolhaScoutSource

ALL_SOURCES = [
    AvtoNetSource(),
    BolhaBackfillSource(),
    BolhaLookaheadSource(),
    BolhaScoutSource(),
]

__all__ = [
    "AvtoNetSource",
    "BolhaLookaheadSource",
    "BolhaBackfillSource",
    "BolhaScoutSource",
    "ALL_SOURCES",
]
