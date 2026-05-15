from scraper.sources.avto_net import AvtoNetSource
from scraper.sources.bolha import BolhaSource

ALL_SOURCES = [AvtoNetSource(), BolhaSource()]

__all__ = ["AvtoNetSource", "BolhaSource", "ALL_SOURCES"]
