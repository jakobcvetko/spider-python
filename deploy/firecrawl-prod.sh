#!/usr/bin/env bash
# Deploy / verify self-hosted Firecrawl on the prod VPS (run on server as deploy user).
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/spider}"
COMPOSE_FILE="${APP_DIR}/docker-compose.firecrawl.prod.yml"
ENV_FILE="${APP_DIR}/.env"
TEST_URL="${TEST_URL:-https://www.avto.net/Ads/details.asp?id=22421750}"

cd "$APP_DIR"

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "Missing $COMPOSE_FILE — copy from repo first." >&2
  exit 1
fi

if ! docker network inspect spider_default >/dev/null 2>&1; then
  echo "Network spider_default not found — start spider stack first:" >&2
  echo "  docker compose -f docker-compose.prod.yml up -d" >&2
  exit 1
fi

echo "==> Pulling Firecrawl images..."
docker compose -f "$COMPOSE_FILE" pull

echo "==> Starting Firecrawl..."
docker compose -f "$COMPOSE_FILE" up -d

echo "==> Waiting for API on 127.0.0.1:3002 (up to 5 min)..."
ready=0
for i in $(seq 1 30); do
  if curl -sf -o /dev/null -X POST "http://127.0.0.1:3002/v2/scrape" \
    -H 'Content-Type: application/json' \
    -d '{"url":"https://example.com","formats":["html"]}'; then
    ready=1
    break
  fi
  echo "  still starting ($i/30)..."
  sleep 10
done

if [[ "$ready" -ne 1 ]]; then
  echo "ERROR: Firecrawl API not ready — logs:" >&2
  docker compose -f "$COMPOSE_FILE" logs --tail=80 firecrawl-api >&2
  exit 1
fi

echo "==> Smoke test from spider-api container..."
docker compose -f docker-compose.prod.yml exec -T api python -c "
import asyncio, os, json
import httpx

async def main():
    url = os.environ.get('FIRECRAWL_API_URL', 'http://firecrawl-api:3002').rstrip('/') + '/v2/scrape'
    payload = {'url': '${TEST_URL}', 'formats': ['html']}
    async with httpx.AsyncClient(timeout=120.0) as c:
        r = await c.post(url, json=payload)
        print('status', r.status_code)
        data = r.json()
        ok = data.get('success')
        html = (data.get('data') or {}).get('html') or ''
        title = (data.get('data') or {}).get('metadata', {}).get('title', '')
        print('success', ok, 'html_bytes', len(html), 'title', (title or '')[:80])
        if r.status_code >= 400 or not ok:
            raise SystemExit(1)

asyncio.run(main())
"

echo "==> Firecrawl OK"
docker compose -f "$COMPOSE_FILE" ps
