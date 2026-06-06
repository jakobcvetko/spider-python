# Spider

Monorepo for the Spider app: a FastAPI backend, a React (Vite + TS) frontend,
and a background scraper worker that polls avto.net and bolha.com and stores
new listings in Postgres.

> **Working with an AI coding agent on this repo?** Start with
> [`AGENTS.md`](./AGENTS.md) — it contains the architecture summary, repo map,
> and conventions/gotchas that Cursor, Claude Code, Codex, Aider, etc. should
> read before editing.

## Stack

- **Backend**: FastAPI · SQLAlchemy 2 (async) · Alembic · asyncpg · Pydantic v2 · Argon2 · `uv`
- **Auth**: HTTP-only session cookies, sessions persisted in Postgres
- **Scrapers**: APScheduler · httpx · selectolax (separate worker processes: lookahead, backfill)
- **Matcher**: separate worker; Postgres `matcher_jobs` NOTIFY
- **Frontend**: Vite · React 19 · TypeScript · Tailwind CSS v4 · React Router · TanStack Query · Axios
- **Dev infra**: Docker Compose (Postgres 16 on host port **5435**)
- **Prod infra**: Hetzner VPS · Docker Compose · Caddy · GitHub Actions → GHCR

## Layout

```
spider-python/
├── backend/                 # FastAPI, scraper, matcher, alembic
├── frontend/                # Vite + React + TS
├── deploy/                  # production bootstrap, Caddy, env template
├── docker-compose.yml       # dev Postgres only
├── docker-compose.prod.yml  # production stack
├── Dockerfile               # prod image (frontend + backend)
├── .github/workflows/       # CI/CD deploy to Hetzner
├── scripts/dev.sh
├── Makefile
└── .env.example
```

## Prerequisites

- Docker Desktop
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Node.js 20+ and npm

## Quick start

```bash
cp .env.example .env
make install     # installs backend (uv) and frontend (npm) deps
make dev         # starts db, runs migrations, then runs backend + frontend (scrapers: separate)
```

Open <http://127.0.0.1:5173>, register an account, and you're in.

## Make commands

| Command | What it does |
|---|---|
| `make help` | List all available commands |
| `make install` | Install backend (uv sync) and frontend (npm install) deps |
| `make dev` | Start Postgres, run migrations, then start backend + frontend with prefixed logs. Ctrl+C stops everything. Scrapers are separate (see Bolha rows below). |
| `make be` | Run backend API only on `:8000` |
| `make fe` | Run frontend dev server only on `:5173` |
| `make bolha:lookahead` | Run the Bolha lookahead scraper worker only |
| `make bolha:backfill` | Run the Bolha backfill scraper worker only |
| `make matcher` | Run the matcher worker (listing → scraper matches) |
| `make avtonet` | Placeholder for a future avto.net–only worker (not wired yet) |
| `make migrate` | Apply pending Alembic migrations |
| `make migration name="add foo column"` | Create a new auto-generated migration |
| `make db-up` / `make db-down` | Start / stop Postgres container |
| `make db-shell` | Open psql against the dev database |
| `make db-reset` | DROP volume and re-apply all migrations (destructive) |
| `make stop` | Stop Postgres container |

## Configuration

Copy `.env.example` → `.env` and adjust as needed. The Postgres host port
defaults to **5435** (5432 was already taken on this machine).

| Var | Default |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://spider:spider@localhost:5435/spider` |
| `SESSION_COOKIE_NAME` | `spider_session` |
| `SESSION_LIFETIME_DAYS` | `14` |
| `CORS_ORIGINS` | `http://localhost:5173` |
| `SCRAPE_INTERVAL_SECONDS` | `60` |
| `SCRAPER_USER_AGENT` | `spider-bot/0.1 (+https://example.com)` |

## API

All routes are mounted under `/api`. Auth is via HTTP-only cookie.

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/auth/register` | Create account; sets session cookie |
| `POST` | `/api/auth/login` | Log in; sets session cookie |
| `POST` | `/api/auth/logout` | Invalidate session and clear cookie |
| `GET`  | `/api/auth/me` | Current user (401 if not logged in) |
| `GET`  | `/api/listings?source=&limit=` | Recent scraped listings (auth required) |
| `GET`  | `/api/health` | Health check |

OpenAPI docs available at <http://127.0.0.1:8000/docs> when the backend is running.

## Production

Staging runs on a **Hetzner VPS** at `46.224.37.205`, served at **https://new.spider.si**
(when DNS points there). Later cutover to `spider.si`. The same host also runs
**Twenty CRM** (`https://crm.spider.si`) and **n8n** (`https://n8n.spider.si`) as
separate Docker Compose stacks behind the shared Caddy reverse proxy.

| What | How |
|------|-----|
| SSH | `ssh spider.si` (see `~/.ssh/config` — host `46.224.37.205`, user `root`) |
| App on server | `/opt/spider` — `docker compose -f docker-compose.prod.yml …` |
| Twenty CRM | `docker-compose.twenty.prod.yml` — `bash deploy/twenty-prod.sh` on VPS |
| n8n | `docker-compose.n8n.prod.yml` — `bash deploy/n8n-prod.sh` on VPS |
| Deploy | Push to `main` / `master` → GitHub Actions builds image → GHCR → SSH deploy |
| Full ops guide | [`deploy/README.md`](./deploy/README.md) |
| Agent / ops cheat sheet | [`AGENTS.md` §9](./AGENTS.md#9-production-server-cicd-and-operations) (§9.7 for Twenty/n8n) |

**Quick checks**

```bash
curl -sS https://new.spider.si/api/health
ssh spider.si 'docker compose -f /opt/spider/docker-compose.prod.yml ps'
ssh spider.si 'docker compose -f /opt/spider/docker-compose.prod.yml logs -f worker-lookahead'
ssh spider.si 'docker exec -it spider-db-1 psql -U spider -d spider'
```

CI/CD needs GitHub Actions secrets: `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`,
`DEPLOY_PATH`, `GHCR_PULL_TOKEN` — see [`deploy/README.md`](./deploy/README.md).

**DNS** is managed in Cloudflare (zone `spider.si`). API token in local `.env`
(`CLOUDFLARE_API_TOKEN`); agents read it with `grep CLOUDFLARE .env` — see
[`AGENTS.md` §9.6](./AGENTS.md#96-cloudflare-dns-spidersi).

## How it works (runtime)

In **development**, `make dev` runs Postgres + API + Vite frontend. Scrapers and
matcher are started separately (`make bolha:lookahead`, `make bolha:backfill`,
`make matcher`).

In **production**, one Docker image runs as five app services plus Caddy and Postgres:

1. **api** — FastAPI + built React (`/api/*` + static files)
2. **worker-lookahead** — probes new Bolha ad IDs ahead of the anchor
3. **worker-backfill** — retries ads in the fallback pipeline
4. **worker-matcher** — matches listings to user scrapers
5. **db** — Postgres 16

Processes talk through the **same database** using Postgres `LISTEN`/`NOTIFY`
(admin live events, matcher jobs). No Redis.

## Scraper notes

Scrapers run as **separate processes** (`scraper/worker.py`, e.g. `make bolha:lookahead`).
Each worker loads only the sources you pass with `--sources` (see the Makefile).
APScheduler triggers each loaded source every `SCRAPE_INTERVAL_SECONDS` (default **60s**)
with per-source jitter, and dedupes by `(source, external_id)` via Postgres
`ON CONFLICT DO NOTHING`.

The current avto.net / bolha.com fetchers will need real-world tuning:

- **avto.net** has Cloudflare-style WAF protection and currently returns 403 to
  plain HTTP requests. Likely needs Playwright (or smarter headers + slower
  request rate) to fetch HTML.
- **bolha.com** redirects through `validate.perfdrive.com` (PerimeterX). The
  search URL/path also needs adjusting to the right category.

Both sources are cleanly isolated under `backend/scraper/sources/` so the
extraction logic can be iterated without touching the orchestration.

## Notes

- Initial migration is already in `backend/alembic/versions/`. New schema
  changes: edit models, then `make migration name="..."` and `make migrate`.
- The frontend dev server proxies `/api/*` to `127.0.0.1:8000`, so cookies
  work without CORS preflight in development.
- Sessions are stored in Postgres (`sessions` table) keyed by SHA-256 of the
  random token; the raw token only ever lives in the user's cookie.
