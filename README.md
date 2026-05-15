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
- **Scraper**: APScheduler · httpx · selectolax (separate worker process)
- **Frontend**: Vite · React 18 · TypeScript · Tailwind CSS v4 · React Router · TanStack Query · Axios
- **Infra**: Docker Compose (Postgres 16)

## Layout

```
spider-python/
├── backend/        # FastAPI app, scraper worker, alembic migrations
│   ├── app/
│   ├── scraper/
│   └── alembic/
├── frontend/       # Vite + React + TS app
├── scripts/dev.sh  # used by `make dev`
├── docker-compose.yml
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
make dev         # starts db, runs migrations, then runs backend + frontend + scraper
```

Open <http://127.0.0.1:5173>, register an account, and you're in.

## Make commands

| Command | What it does |
|---|---|
| `make help` | List all available commands |
| `make install` | Install backend (uv sync) and frontend (npm install) deps |
| `make dev` | Start Postgres, run migrations, then start backend + frontend + scraper with prefixed logs. Ctrl+C stops everything. |
| `make be` | Run backend API only on `:8000` |
| `make fe` | Run frontend dev server only on `:5173` |
| `make scraper` | Run scraper worker only |
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

## Scraper notes

The scraper runs as a **separate process** (`scraper/worker.py`) and shares the
backend's models/DB pool. APScheduler triggers each source at
`SCRAPE_INTERVAL_SECONDS` (default **60s**) with per-source jitter, and dedupes
by `(source, external_id)` via a Postgres unique constraint + `ON CONFLICT DO NOTHING`.

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
