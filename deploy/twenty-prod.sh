#!/usr/bin/env bash
# Deploy / verify self-hosted Twenty CRM on the prod VPS (run on server as deploy user).
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/spider}"
COMPOSE_FILE="${APP_DIR}/docker-compose.twenty.prod.yml"
ENV_FILE="${APP_DIR}/.env"

cd "$APP_DIR"

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "Missing $COMPOSE_FILE — copy from repo first." >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE" >&2
  exit 1
fi

missing=()
for var in TWENTY_SERVER_URL TWENTY_PG_PASSWORD TWENTY_ENCRYPTION_KEY TWENTY_DOMAIN; do
  val="$(grep -E "^${var}=" "$ENV_FILE" | head -1 | cut -d= -f2- || true)"
  if [[ -z "$val" ]]; then
    missing+=("$var")
  fi
done
if [[ ${#missing[@]} -gt 0 ]]; then
  echo "Missing required env vars in $ENV_FILE: ${missing[*]}" >&2
  exit 1
fi

if ! docker network inspect spider_default >/dev/null 2>&1; then
  echo "Network spider_default not found — start spider stack first:" >&2
  echo "  docker compose -f docker-compose.prod.yml up -d" >&2
  exit 1
fi

echo "==> Pulling Twenty images..."
docker compose -f "$COMPOSE_FILE" pull

echo "==> Starting Twenty..."
docker compose -f "$COMPOSE_FILE" up -d

echo "==> Waiting for Twenty healthz (up to 5 min)..."
ready=0
for i in $(seq 1 30); do
  if docker run --rm --network spider_default curlimages/curl:8.12.1 \
    -sf "http://twenty-server:3000/healthz" >/dev/null; then
    ready=1
    break
  fi
  echo "  still starting ($i/30)..."
  sleep 10
done

if [[ "$ready" -ne 1 ]]; then
  echo "ERROR: Twenty not healthy — logs:" >&2
  docker compose -f "$COMPOSE_FILE" logs --tail=80 twenty-server >&2
  exit 1
fi

echo "==> Recreating Caddy (pick up TWENTY_DOMAIN)..."
docker compose -f docker-compose.prod.yml up -d --force-recreate caddy

echo "==> Twenty OK at $(grep -E '^TWENTY_SERVER_URL=' "$ENV_FILE" | head -1 | cut -d= -f2-)"
docker compose -f "$COMPOSE_FILE" ps
