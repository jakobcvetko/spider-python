from datetime import datetime, timezone

from scraper.publish_dates import parse_avtonet_published_at, parse_bolha_published_at


def test_parse_bolha_published_at() -> None:
    html = """
    <dt class="ClassifiedDetailSystemDetails-listTerm">
        Oglas je objavljen
    </dt>
    <dd class="ClassifiedDetailSystemDetails-listData">
        17.05.2026. ob 21:52
    </dd>
    """
    got = parse_bolha_published_at(html)
    assert got is not None
    assert got.tzinfo == timezone.utc


def test_parse_avtonet_published_at() -> None:
    html = '<div>Zadnja sprememba: 17.5.2026 21:51:00</motion.div>'
    got = parse_avtonet_published_at(html)
    assert got is not None
    assert got == datetime(2026, 5, 17, 19, 51, tzinfo=timezone.utc)
