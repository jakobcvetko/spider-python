import httpx

from scraper.sources.bolha_common import classify_probe_response


def _resp(
    *,
    status: int,
    url: str,
    html: str = "",
) -> httpx.Response:
    return httpx.Response(status, request=httpx.Request("GET", url), text=html)


def test_classify_inactive_listing_as_active() -> None:
    ad_id = 15_935_188
    html = (
        '"name":"GTMTracking","adStatus":"inactive",'
        '<meta property="og:title" content="New Balance RC 42">'
    )
    resp = _resp(
        status=200,
        url=(
            "https://iapi.bolha.com/obutev-za-prosti-cas-zenska-oblacila-obutev/"
            f"new-balance-rc-42-oglas-{ad_id}"
        ),
        html=html,
    )
    kind, gtm, _detail, http_st = classify_probe_response(resp, html, ad_id=ad_id)
    assert http_st == 200
    assert gtm == "inactive"
    assert kind == "active"


def test_classify_gtm_expired_redirect_as_expired() -> None:
    ad_id = 15_000_000
    html = '"name":"GTMTracking","adStatus":"expired"'
    resp = _resp(
        status=200,
        url=f"https://iapi.bolha.com/lov-ostalo/lovski-zimski-pulover-nov-oglas-{ad_id}",
        html=html,
    )
    kind, gtm, _detail, _http_st = classify_probe_response(resp, html, ad_id=ad_id)
    assert gtm == "expired"
    assert kind == "expired"


def test_classify_not_yet_created_404() -> None:
    ad_id = 15_999_999
    resp = _resp(
        status=404,
        url=f"https://iapi.bolha.com/avtomobili/progressive-scrape-oglas-{ad_id}",
    )
    kind, gtm, _detail, http_st = classify_probe_response(resp, "", ad_id=ad_id)
    assert http_st == 404
    assert gtm is None
    assert kind == "not_yet_created"
