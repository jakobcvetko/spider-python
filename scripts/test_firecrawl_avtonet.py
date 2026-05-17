#!/usr/bin/env python3
"""One-off: can Firecrawl fetch avto.net listing pages?

Usage (from repo root):
  cd backend && FIRECRAWL_API_KEY=fc-... uv run python ../scripts/test_firecrawl_avtonet.py
  cd backend && FIRECRAWL_API_KEY=fc-... uv run python ../scripts/test_firecrawl_avtonet.py --start-id 22421224 --count 10
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

# Reuse avto.net page heuristics (no Firecrawl integration).
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from scraper.sources.avto_net_common import classify_detail, detail_url  # noqa: E402

def scrape_one(
    client: httpx.Client, api_url: str, api_key: str | None, ad_id: int
) -> dict:
    from scraper.firecrawl import scrape_endpoint

    url = detail_url(ad_id)
    endpoint = scrape_endpoint(api_url)
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    t0 = time.perf_counter()
    resp = client.post(
        endpoint,
        headers=headers,
        json={
            "url": url,
            "formats": ["html"],
            "onlyMainContent": False,
        },
    )
    elapsed_ms = round((time.perf_counter() - t0) * 1000)
    out: dict = {
        "ad_id": ad_id,
        "url": url,
        "http_status": resp.status_code,
        "elapsed_ms": elapsed_ms,
    }
    try:
        payload = resp.json()
    except json.JSONDecodeError:
        out["error"] = resp.text[:300]
        out["outcome"] = "api_error"
        return out

    if resp.status_code >= 400:
        out["error"] = str(payload)[:300]
        out["outcome"] = "api_error"
        return out

    if not payload.get("success"):
        out["error"] = str(payload.get("error") or payload)[:300]
        out["outcome"] = "api_error"
        return out

    data = payload.get("data") or {}
    meta = data.get("metadata") or {}
    html = data.get("html") or ""
    page_status = meta.get("statusCode") or meta.get("status") or 200
    out["page_status"] = page_status
    out["html_len"] = len(html)
    out["title"] = (meta.get("title") or "")[:80]

    doc_title = meta.get("title")
    if isinstance(doc_title, str):
        doc_title = doc_title.strip() or None
    else:
        doc_title = None
    kind, detail = classify_detail(
        html,
        int(page_status) if page_status else 200,
        meta.get("sourceURL") or meta.get("url") or url,
        httpx.Headers(),
        ad_id=ad_id,
        document_title=doc_title,
    )
    out["outcome"] = kind
    out["detail"] = detail
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Test Firecrawl on avto.net ads")
    parser.add_argument("--start-id", type=int, default=22_421_224)
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between requests")
    args = parser.parse_args()

    api_key = os.environ.get("FIRECRAWL_API_KEY", "").strip() or None
    api_url = os.environ.get(
        "FIRECRAWL_API_URL", "https://api.firecrawl.dev"
    ).strip()
    if not api_key and api_url.rstrip("/") == "https://api.firecrawl.dev":
        print("Set FIRECRAWL_API_KEY or FIRECRAWL_API_URL (self-hosted)", file=sys.stderr)
        return 2

    results: list[dict] = []
    with httpx.Client(timeout=120.0) as client:
        for i in range(1, args.count + 1):
            ad_id = args.start_id + i
            if i > 1 and args.delay > 0:
                time.sleep(args.delay)
            results.append(scrape_one(client, api_url, api_key, ad_id))

    active = sum(1 for r in results if r.get("outcome") == "active")
    blocked = sum(1 for r in results if r.get("outcome") in ("cloudflare", "blocked"))
    api_err = sum(1 for r in results if r.get("outcome") == "api_error")
    not_found = sum(1 for r in results if r.get("outcome") == "not_found")

    print()
    print(f"Firecrawl avto.net test  start={args.start_id + 1}  count={args.count}")
    print(f"  active      {active}")
    print(f"  not_found   {not_found}")
    print(f"  blocked/cf  {blocked}")
    print(f"  api_error   {api_err}")
    print()
    for r in results:
        title = f"  title={r['title']!r}" if r.get("title") else ""
        extra = f"  ({r['detail']})" if r.get("detail") else ""
        err = f"  err={r['error'][:80]}" if r.get("error") else ""
        print(
            f"  id={r['ad_id']}  api={r['http_status']}  page={r.get('page_status', '?')}  "
            f"{r.get('outcome', '?')}  {r['elapsed_ms']}ms  len={r.get('html_len', 0)}{title}{extra}{err}"
        )

    return 0 if active >= args.count // 2 else (2 if blocked + api_err >= args.count else 1)


if __name__ == "__main__":
    raise SystemExit(main())
