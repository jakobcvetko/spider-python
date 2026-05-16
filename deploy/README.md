# Hetzner deployment + GitHub Actions CD

Pushing to **`main`** or **`master`** builds a Docker image, pushes it to **GHCR**, and deploys to your Hetzner VPS over SSH.

## Architecture

| Service | Role |
|---------|------|
| `api` | FastAPI + built React (`/api/*` + static SPA) |
| `worker-lookahead` | Bolha frontier scraper |
| `worker-backfill` | Bolha backfill scraper |
| `worker-matcher` | Listing matcher |
| `db` | Postgres 16 (persistent volume) |
| `caddy` | HTTPS reverse proxy → `api` |

All app containers share one image; only the command differs.

## 1. Hetzner VPS (one-time)

1. Create an Ubuntu 24.04 server (CX22 or larger is plenty).
2. Point your domain **A/AAAA** record at the server IP.
3. SSH as root and run bootstrap:

```bash
export DEPLOY_USER=deploy
export APP_DIR=/opt/spider
# clone or copy deploy/bootstrap.sh, then:
sudo bash deploy/bootstrap.sh
```

4. Add your deploy key:

```bash
sudo -u deploy mkdir -p ~deploy/.ssh
sudo -u deploy nano ~deploy/.ssh/authorized_keys
```

5. Copy compose templates and create `.env`:

```bash
sudo -u deploy mkdir -p /opt/spider/deploy
# After first CI run, files land here automatically. For first boot, copy from repo:
# docker-compose.prod.yml, deploy/Caddyfile, deploy/env.example → /opt/spider/
sudo -u deploy cp /opt/spider/deploy/env.example /opt/spider/.env
sudo -u deploy nano /opt/spider/.env
```

Required `.env` values:

| Variable | Example |
|----------|---------|
| `SPIDER_IMAGE` | `ghcr.io/youruser/spider-python` (lowercase) |
| `POSTGRES_PASSWORD` | long random string |
| `DOMAIN` | `spider.example.com` |
| `ACME_EMAIL` | your email (Let's Encrypt) |
| `SESSION_COOKIE_SECURE` | `true` |
| `CORS_ORIGINS` | `https://spider.example.com` |

Open firewall: **22**, **80**, **443**.

## 2. GitHub Container Registry

After the first workflow run, the image appears under **Packages** on GitHub.

For a **private** repo/package, create a PAT with `read:packages` and store it as **`GHCR_PULL_TOKEN`**.

Alternatively: Package → Package settings → **Change visibility** → public (then `GHCR_PULL_TOKEN` can be any valid PAT or omitted if you adjust the workflow).

`SPIDER_IMAGE` on the server must match the pushed image path (lowercase):

`ghcr.io/<github-owner>/<repo-name>`

## 3. GitHub Actions secrets

Repository → **Settings** → **Secrets and variables** → **Actions**:

| Secret | Value |
|--------|--------|
| `DEPLOY_HOST` | Server IP or hostname |
| `DEPLOY_USER` | `deploy` |
| `DEPLOY_SSH_KEY` | Private SSH key (PEM) |
| `DEPLOY_PATH` | `/opt/spider` |
| `GHCR_PULL_TOKEN` | PAT with `read:packages` (private images) |

## 4. Deploy flow

Each push to `main` / `master`:

1. Build `Dockerfile` (frontend + backend).
2. Push `ghcr.io/<owner>/<repo>:latest` and `:<sha>`.
3. SCP `docker-compose.prod.yml` + `deploy/` to the server.
4. SSH: `docker compose pull` → `up -d` → `alembic upgrade head`.

Manual deploy: **Actions** → **Deploy** → **Run workflow**.

## 5. Verify

```bash
curl -sS "https://${DOMAIN}/api/health"
```

Register a user, confirm admin scraper WebSocket on `/api/admin/scraper/ws`.

## Local production smoke test

```bash
cp deploy/env.example .env.prod
# edit POSTGRES_PASSWORD, set DOMAIN=localhost for a quick test, etc.
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

## Troubleshooting

- **Caddy won't start** — `DOMAIN` must be set and DNS must resolve to this host.
- **401 / cookies** — `SESSION_COOKIE_SECURE=true` requires HTTPS; `CORS_ORIGINS` must match your public URL.
- **Workers idle** — all processes need the same `DATABASE_URL` (compose sets this from `POSTGRES_PASSWORD`).
- **GHCR pull denied** — check `GHCR_PULL_TOKEN` and that `SPIDER_IMAGE` matches the package name (lowercase).
