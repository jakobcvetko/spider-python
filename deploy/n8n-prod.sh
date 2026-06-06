#!/usr/bin/env bash
# Deploy / verify self-hosted n8n on the prod VPS (run on server as deploy user).
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/spider}"
COMPOSE_FILE="${APP_DIR}/docker-compose.n8n.prod.yml"
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
for var in N8N_DOMAIN N8N_HOST N8N_WEBHOOK_URL N8N_PG_PASSWORD N8N_ENCRYPTION_KEY N8N_JWT_SECRET; do
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

echo "==> Pulling n8n images..."
docker compose -f "$COMPOSE_FILE" pull

echo "==> Starting n8n..."
docker compose -f "$COMPOSE_FILE" up -d

echo "==> Waiting for n8n healthz (up to 5 min)..."
ready=0
for i in $(seq 1 30); do
  if docker run --rm --network spider_default curlimages/curl:8.12.1 \
    -sf "http://n8n:5678/healthz" >/dev/null; then
    ready=1
    break
  fi
  echo "  still starting ($i/30)..."
  sleep 10
done

if [[ "$ready" -ne 1 ]]; then
  echo "ERROR: n8n not healthy — logs:" >&2
  docker compose -f "$COMPOSE_FILE" logs --tail=80 n8n >&2
  exit 1
fi

echo "==> Recreating Caddy (pick up N8N_DOMAIN)..."
docker compose -f docker-compose.prod.yml up -d --force-recreate caddy

echo "==> n8n OK at $(grep -E '^N8N_WEBHOOK_URL=' "$ENV_FILE" | head -1 | cut -d= -f2-)"
docker compose -f "$COMPOSE_FILE" ps
