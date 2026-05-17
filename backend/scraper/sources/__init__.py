from scraper.sources.avto_net import AvtoNetSource
from scraper.sources.avto_net_lookahead import AvtoNetLookaheadSource
from scraper.sources.avto_net_scout import AvtoNetScoutSource
from scraper.sources.bolha_backfill import BolhaBackfillSource
from scraper.sources.bolha_lookahead import BolhaLookaheadSource
from scraper.sources.bolha_scout import BolhaScoutSource

ALL_SOURCES = [
    AvtoNetSource(),
    AvtoNetLookaheadSource(),
    AvtoNetScoutSource(),
    BolhaBackfillSource(),
    BolhaLookaheadSource(),
    BolhaScoutSource(),
]

__all__ = [
    "AvtoNetSource",
    "AvtoNetLookaheadSource",
    "AvtoNetScoutSource",
    "BolhaLookaheadSource",
    "BolhaBackfillSource",
    "BolhaScoutSource",
    "ALL_SOURCES",
]
