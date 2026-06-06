# Production deployment (Hetzner)

Spider production runs on a Hetzner VPS using Docker Compose. Pushes to **`main`**
or **`master`** trigger GitHub Actions to build, push to GHCR, and deploy over SSH.

For AI agents: full production cheat sheet is in [`AGENTS.md` §9](../AGENTS.md#9-production-server-cicd-and-operations).

---

## Server

| Item | Value |
|------|--------|
| IP | `46.224.37.205` |
| SSH (admin) | `ssh spider.si` → `HostName 46.224.37.205`, user `root` |
| SSH (CI) | `deploy@46.224.37.205` |
| App path | `/opt/spider` |
| Staging URL | https://new.spider.si |
| Twenty CRM | https://crm.spider.si |
| n8n | https://n8n.spider.si |
| Portainer | https://admin-dash.spider.si |
| Image | `ghcr.io/jakobcvetko/spider-python` |

DNS: `new.spider.si` **A** → `46.224.37.205` (required for HTTPS / Let's Encrypt).
Managed in **Cloudflare** (zone `spider.si`). API token: repo-root `.env`
`CLOUDFLARE_API_TOKEN` — see [`AGENTS.md` §9.6](../AGENTS.md#96-cloudflare-dns-spidersi).

---

## Architecture

| Service | Command / role |
|---------|----------------|
| `api` | `uvicorn app.main:app` — API + React static files |
| `worker-lookahead` | `python -m scraper.worker --sources bolha.lookahead` |
| `worker-backfill` | `python -m scraper.worker --sources bolha.backfill` |
| `worker-matcher` | `python -m matcher.worker` |
| `worker-avtonet` | `python -m scraper.worker --sources avto.net.lookahead` (needs Firecrawl) |
| `db` | Postgres 16 (persistent volume) |
| `caddy` | HTTPS reverse proxy → `api`, Twenty, n8n, Portainer (`deploy/Caddyfile`) |
| `portainer` | Docker management UI at `admin-dash.spider.si` |

**Self-hosted Twenty CRM** (`crm.spider.si`, separate compose — not started by CI):

```bash
cd /opt/spider
# Set TWENTY_* vars in .env first (see deploy/env.example)
bash deploy/twenty-prod.sh
```

**Self-hosted n8n** (`n8n.spider.si`, separate compose — not started by CI):

```bash
cd /opt/spider
# Set N8N_* vars in .env first (see deploy/env.example)
bash deploy/n8n-prod.sh
```

n8n includes the `@linkedpromo/n8n-nodes-twenty` community package. Twenty API
credentials in n8n: URL `https://crm.spider.si` (no `/rest` suffix); API key from
Twenty → Settings → Developers → API & Webhooks.

**Self-hosted Firecrawl** (separate compose, not deployed by CI automatically):

```bash
# On the VPS after spider stack is up
cd /opt/spider
bash deploy/firecrawl-prod.sh
```

Set in `/opt/spider/.env`: `FIRECRAWL_API_URL=http://firecrawl-api:3002`, `AVTONET_FETCH_MODE=firecrawl`.
Then recreate app containers: `docker compose -f docker-compose.prod.yml up -d --force-recreate`.

All workers share the production Postgres DB and use `LISTEN`/`NOTIFY` (see `AGENTS.md`).

---

## CI/CD

**Workflow:** `.github/workflows/deploy.yml`

**On each push to `main` / `master`:**

1. Build `Dockerfile` (frontend → `backend/public`, Python deps via `uv`).
2. Push `ghcr.io/jakobcvetko/spider-python:latest` and `:<commit-sha>`.
3. Copy `docker-compose.prod.yml`, `docker-compose.twenty.prod.yml`, `docker-compose.n8n.prod.yml`, `docker-compose.firecrawl.prod.yml`, + `deploy/` to `/opt/spider` on the server.
4. SSH: `docker compose pull` → `up -d` → `alembic upgrade head`.

**Manual deploy:** GitHub → Actions → **Deploy** → Run workflow.

### GitHub Actions secrets

| Secret | Example |
|--------|---------|
| `DEPLOY_HOST` | `46.224.37.205` |
| `DEPLOY_USER` | `deploy` |
| `DEPLOY_SSH_KEY` | Private PEM for `deploy@` |
| `DEPLOY_PATH` | `/opt/spider` |
| `GHCR_PULL_TOKEN` | Optional — PAT with `read:packages` (only if GHCR image is private) |

Server `/opt/spider/.env` must include `SPIDER_IMAGE=ghcr.io/jakobcvetko/spider-python`.

---

## First-time server setup

```bash
# On the VPS as root
export DEPLOY_USER=deploy APP_DIR=/opt/spider
sudo bash deploy/bootstrap.sh

# Create .env from template and edit secrets + domain
sudo -u deploy cp /opt/spider/deploy/env.example /opt/spider/.env
sudo -u deploy nano /opt/spider/.env

# Add deploy user's authorized_keys (for GitHub Actions)
sudo -u deploy nano ~deploy/.ssh/authorized_keys
```

Open firewall ports: **22**, **80**, **443**.

---

## Operations

### Container status

```bash
ssh spider.si 'docker compose -f /opt/spider/docker-compose.prod.yml ps'
```

### Logs

```bash
# Follow lookahead scraper
ssh spider.si 'docker compose -f /opt/spider/docker-compose.prod.yml logs -f worker-lookahead'

# Other services: worker-backfill, worker-matcher, api, caddy, db
ssh spider.si 'docker compose -f /opt/spider/docker-compose.prod.yml logs -f api'
```

Filter lookahead for useful lines:

```bash
ssh spider.si 'docker compose -f /opt/spider/docker-compose.prod.yml logs worker-lookahead 2>&1 \
  | grep -E "batch anchor|ERROR|200 OK"'
```

### Health check

```bash
curl -sS https://new.spider.si/api/health
curl -sS -o /dev/null -w '%{http_code}\n' https://crm.spider.si/healthz
curl -sS -o /dev/null -w '%{http_code}\n' https://n8n.spider.si/healthz
```

### Twenty / n8n logs

```bash
ssh spider.si 'cd /opt/spider && docker compose -f docker-compose.twenty.prod.yml logs -f twenty-server'
ssh spider.si 'cd /opt/spider && docker compose -f docker-compose.n8n.prod.yml logs -f n8n'
```

### Production database

```bash
ssh spider.si 'docker exec -it spider-db-1 psql -U spider -d spider'
```

```sql
SELECT status, COUNT(*) FROM bolha_ads GROUP BY status;
SELECT COUNT(*) FROM listings;
SELECT last_working_ad_id, last_fetch_high_water FROM bolha_scrape_meta WHERE id = 1;
```

Password is in `/opt/spider/.env` (`POSTGRES_PASSWORD`).

### Manual deploy (without CI)

```bash
ssh spider.si
cd /opt/spider
export IMAGE_TAG=latest   # or a specific git sha
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d --remove-orphans
docker compose -f docker-compose.prod.yml run --rm --no-deps api alembic upgrade head
```

### After changing domain in `.env`

```bash
docker compose -f /opt/spider/docker-compose.prod.yml up -d --force-recreate api caddy
```

---

## Configuration (`/opt/spider/.env`)

| Variable | Staging example |
|----------|-----------------|
| `SPIDER_IMAGE` | `ghcr.io/jakobcvetko/spider-python` |
| `POSTGRES_PASSWORD` | (long random) |
| `DOMAIN` | `new.spider.si` |
| `ACME_EMAIL` | your email |
| `SESSION_COOKIE_SECURE` | `true` |
| `CORS_ORIGINS` | `https://new.spider.si` |
| `TWENTY_DOMAIN` / `TWENTY_SERVER_URL` | `crm.spider.si` / `https://crm.spider.si` |
| `N8N_DOMAIN` / `N8N_WEBHOOK_URL` | `n8n.spider.si` / `https://n8n.spider.si/` |

Twenty and n8n also need `TWENTY_PG_PASSWORD`, `TWENTY_ENCRYPTION_KEY`,
`N8N_PG_PASSWORD`, `N8N_ENCRYPTION_KEY`, `N8N_JWT_SECRET` — see `deploy/env.example`.

When stable, switch `DOMAIN` / `CORS_ORIGINS` to `spider.si` and recreate `api` + `caddy`.

---

## Local production smoke test

```bash
cp deploy/env.example .env.prod
# edit values
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Caddy won't get TLS | DNS for `DOMAIN` must resolve to this server |
| `401` / cookies broken | `SESSION_COOKIE_SECURE=true` needs HTTPS; `CORS_ORIGINS` must match site URL |
| Workers crash on missing tables | Run `alembic upgrade head`, then restart workers |
| `GHCR pull` denied | Check `GHCR_PULL_TOKEN` and `SPIDER_IMAGE` (lowercase) |
| Lookahead only 404s | Normal ahead of Bolha frontier; check `last_working_ad_id` in `bolha_scrape_meta` |

**Default admin** (change after login): `admin@example.com` / `password`.
