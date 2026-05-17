from scraper.sources.avto_net import AvtoNetSource
from scraper.sources.avto_net_backfill import AvtoNetBackfillSource
from scraper.sources.avto_net_lookahead import AvtoNetLookaheadSource
from scraper.sources.avto_net_scout import AvtoNetScoutSource
from scraper.sources.bolha_backfill import BolhaBackfillSource
from scraper.sources.bolha_lookahead import BolhaLookaheadSource
from scraper.sources.bolha_scout import BolhaScoutSource

ALL_SOURCES = [
    AvtoNetSource(),
    AvtoNetLookaheadSource(),
    AvtoNetBackfillSource(),
    AvtoNetScoutSource(),
    BolhaBackfillSource(),
    BolhaLookaheadSource(),
    BolhaScoutSource(),
]

__all__ = [
    "AvtoNetSource",
    "AvtoNetLookaheadSource",
    "AvtoNetBackfillSource",
    "AvtoNetScoutSource",
    "BolhaLookaheadSource",
    "BolhaBackfillSource",
    "BolhaScoutSource",
    "ALL_SOURCES",
]
