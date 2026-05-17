# AGENTS.md

Project guide for AI coding agents (Cursor, Codex, Claude Code, Aider, Cline, etc.).
Read this **before** making changes. The conventions here exist because of real
behaviors of this codebase — ignoring them creates broken or insecure code.

For human-facing setup instructions, see [`README.md`](./README.md). This file
focuses on what an agent needs to know to work effectively in the repo.

**Production / deploy / logs:** see [§9 Production server, CI/CD, and operations](#9-production-server-cicd-and-operations)
(`ssh spider.si`, `/opt/spider`, `new.spider.si`, GitHub Actions → Hetzner).

**DNS (Cloudflare):** API token in repo-root `.env` — [§9.6](#96-cloudflare-dns-spidersi); read with
`grep CLOUDFLARE_API_TOKEN .env` (never commit or log the value).

---

## 1. What this project is

**Spider** is a small monorepo that scrapes Slovenian classifieds
(`avto.net`, `bolha.com`) and exposes the listings through an authenticated
web app.

- `backend/` — FastAPI + SQLAlchemy 2 (async) + Alembic. **Separate OS processes**:
  API (`app/`), Bolha scraper workers (`scraper/`), matcher (`matcher/`).
- `frontend/` — Vite + React 19 + TypeScript + Tailwind v4 + TanStack Query.
- Postgres 16 — dev: `docker-compose.yml` (host port **5435**); prod: same DB in
  `docker-compose.prod.yml`.

All backend processes share one Postgres database and coordinate via
**`LISTEN`/`NOTIFY`** (no Redis, no message broker):

| Channel | Direction | Purpose |
|---------|-----------|---------|
| `scraper_events` | worker → API | Admin live scraper UI |
| `scraper_commands` | API → worker | Run-now commands |
| `matcher_jobs` | lookahead → matcher | Enqueue listing match after scrape |

**Production** runs five containers from one image: `api`, `worker-lookahead`,
`worker-backfill`, `worker-matcher`, `db`, plus `caddy` for HTTPS. See
[§9 Production](#9-production-server-cicd-and-operations).

---

## 2. Repo layout — where to find things

```
spider-python/
├── backend/
│   ├── app/                       # FastAPI process
│   │   ├── main.py                # app factory, router wiring, lifespan
│   │   ├── config.py              # Pydantic Settings (reads .env)
│   │   ├── database.py            # async engine + SessionLocal
│   │   ├── deps.py                # FastAPI deps: get_current_user, require_admin
│   │   ├── security.py            # argon2 password hashing, session token gen
│   │   ├── scraper_events.py      # LISTEN/NOTIFY event bus (cross-process IPC)
│   │   ├── api/                   # route modules (auth, listings, admin)
│   │   ├── models/                # SQLAlchemy models — register in __init__.py
│   │   └── schemas/               # Pydantic v2 request/response schemas
│   ├── scraper/                   # Standalone worker process
│   │   ├── worker.py              # entrypoint: `uv run python -m scraper.worker [--sources …]`
│   │   ├── base.py                # Source protocol + ScrapedItem + upsert_items
│   │   └── sources/               # one file per site (avto_net.py, bolha.py)
│   ├── alembic/                   # migrations (env.py is async-aware)
│   └── pyproject.toml             # deps managed by uv
├── frontend/
│   └── src/
│       ├── App.tsx                # routes
│       ├── main.tsx               # QueryClient + Router providers
│       ├── lib/                   # api.ts (axios), auth.ts, listings.ts, admin.ts
│       ├── pages/                 # one .tsx per route
│       └── components/            # ProtectedRoute, ui.tsx primitives
├── scripts/dev.sh                 # spawn+supervise be+fe with prefixed logs
├── docker-compose.yml             # dev Postgres only (port 5435)
├── docker-compose.prod.yml        # prod stack (api + workers + db + caddy)
├── Dockerfile                     # multi-stage: frontend build + backend image
├── deploy/                        # Caddyfile, env.example, bootstrap.sh, README
├── .github/workflows/deploy.yml   # push main/master → GHCR → Hetzner SSH
├── Makefile                       # canonical entry point — see `make help`
└── .env.example                   # copy to .env
```

---

## 3. Running the project

**Always use the Makefile.** Don't reinvent the commands; they encode
non-obvious choices (port 5435, healthcheck waits, env loading order, etc.).

| Command | When to use |
|---|---|
| `make install` | First-time setup (runs `uv sync` and `npm install`) |
| `make dev` | Most common. Starts Postgres, runs migrations, then backend (`:8000`) + frontend (`:5173`) with prefixed logs. Ctrl+C cleans everything up via `scripts/dev.sh`. **Does not start scrapers** — use Bolha targets below. |
| `make bolha:lookahead` | Run the Bolha lookahead worker only (`--sources bolha.lookahead`). |
| `make bolha:backfill` | Run the Bolha backfill worker only (`--sources bolha.backfill`). |
| `make bolha:scout` | One-shot: find `last_working_ad_id` via gallop + binary search, update meta, exit. Use when the anchor is far behind the real frontier. |
| `make matcher` | Matcher worker (`matcher.worker`); listens on `matcher_jobs` NOTIFY. |
| `make avtonet` | Placeholder for a future avto.net–only worker (not wired yet). |
| `make be` / `make fe` | Single component, usually for debugging |
| `make migration name="add x column"` | Create autogenerated Alembic migration |
| `make migrate` | Apply pending migrations |
| `make db-shell` | psql into the dev database |
| `make db-reset` | Drop the volume and re-migrate (destructive) |

There is no test suite yet. If you add one, wire it through `make test` and
update this file.

### Backend commands

Always run backend commands through **`uv run`**, never bare `python` or `pip`:

```bash
cd backend
uv run python -m scraper.worker --sources bolha.lookahead
uv run python -m scraper.worker --sources bolha.backfill
uv run python -m scraper.worker --sources bolha.scout
uv run alembic revision --autogenerate -m "..."
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

### Frontend commands

Standard `npm` from `frontend/`:

```bash
cd frontend
npm run dev      # vite
npm run build    # tsc -b && vite build
npm run lint     # eslint .
```

---

## 4. Critical conventions & gotchas

These are the things that bite agents most often. Read them.

### 4.1 Two processes, one database

The API (`app/main.py`) and the scraper (`scraper/worker.py`) are separate
processes. They share:

- The same SQLAlchemy models (`backend/app/models/`)
- The same Postgres database (via `DATABASE_URL`)
- Two `pg_notify` channels: `scraper_events` (worker → API) and
  `scraper_commands` (API → worker)

If you add cross-process state, prefer extending the existing event bus in
`app/scraper_events.py` over inventing new IPC. **Do not add Redis or any
broker** — the design intentionally avoids one.

### 4.2 Async everything in the backend

SQLAlchemy 2.0 async + asyncpg. Inside `app/` and `scraper/`:

- Use `AsyncSession`, `await db.execute(...)`, `await db.commit()`.
- Endpoints that need the DB take `db: AsyncSession = Depends(get_db)`.
- Background tasks open a session with `async with SessionLocal() as db:`.
- Never call sync SQLAlchemy APIs (`session.query`, `session.commit()` without
  `await`, etc.) — they will silently break under asyncpg.

### 4.3 New models MUST be registered

`backend/app/models/__init__.py` re-exports every model. **If you don't add a
new model there, Alembic `--autogenerate` will not see it** and your migration
will be empty/wrong. Pattern:

```44:50:backend/alembic/env.py
from app.config import get_settings
from app.models import Base  # noqa: F401  (registers all models with Base.metadata)

config = context.config
```

After adding/changing a model, run `make migration name="describe change"` and
review the generated file before applying.

### 4.4 Database port is 5435 (not 5432)

`docker-compose.yml` maps host `5435` → container `5432`. The default
`.env.example` already reflects this. If you write code or scripts that
hard-code `5432`, you'll connect to whatever else is running on that port.

### 4.5 Sessions: never log the raw token

Auth flow:

1. `secrets.token_urlsafe(48)` generates the session token.
2. **Only the SHA-256 hash** is stored in the `sessions` table.
3. The raw token lives only in the user's HTTP-only cookie (default
   `spider_session`, configurable via `SESSION_COOKIE_NAME`).

When debugging auth, log the *hash* or the cookie name — never the raw token.
See `backend/app/api/auth.py` and `backend/app/deps.py`.

### 4.6 Scrapers currently fail against live sites

This is by design / known limitation, **not a bug for an agent to chase**:

- **avto.net** sits behind a Cloudflare-style WAF → returns 403 to plain
  HTTP. Real fix is Playwright or carefully tuned headers/rate limits.
- **bolha.com** redirects through `validate.perfdrive.com` (PerimeterX). The
  search URL also points at the wrong category and needs adjustment.

Both fetchers in `backend/scraper/sources/` are best-effort; don't assume the
extraction logic is correct just because it parses without errors. If you're
asked to "make scraping work", you need to address the WAF/redirect first.

### 4.7 Frontend talks to backend through a Vite proxy

In dev, `frontend/vite.config.ts` proxies `/api/*` (and websockets) to
`127.0.0.1:8000`. Therefore:

- Always use **relative paths** (`/api/...`), never absolute URLs to
  `localhost:8000`. The shared `axios` client already does this:

  ```1:7:frontend/src/lib/api.ts
  import axios from 'axios'

  export const api = axios.create({
    baseURL: '/api',
    withCredentials: true,
  })
  ```

- `withCredentials: true` is required everywhere for the session cookie.
- The admin scraper events endpoint is a WebSocket at `/api/admin/scraper/ws`
  — it relies on the proxy's `ws: true` setting in dev.

### 4.8 Tailwind is v4 (no config file)

There is no `tailwind.config.js`. Tailwind v4 is configured via the
`@tailwindcss/vite` plugin and `frontend/src/index.css`. If you find docs
saying "edit your `tailwind.config.js`", you're on the wrong major version.

### 4.9 React Query is the source of truth for server state

Use the existing `useMe`, `useLogin`, `useLogout`, listing/admin hooks in
`frontend/src/lib/`. Don't sprinkle `axios` calls and `useState` into pages —
extend the hook layer instead. Mutations should call
`queryClient.invalidateQueries` / `setQueryData` for the relevant keys.

### 4.10 Admin gating

`require_admin` (in `app/deps.py`) is the only thing protecting admin routes.
The first admin user is seeded in
`backend/alembic/versions/8a1f2b3c9d77_add_is_admin_and_seed_admin_user.py`.
WebSocket auth uses `get_admin_user_from_cookie` because `Depends` doesn't
fire on the WS handshake the same way.

### 4.11 `ALEMBIC_DATABASE_URL` is currently unused

`alembic/env.py` reads `settings.database_url` (the asyncpg URL) and uses
`async_engine_from_config`. The `ALEMBIC_DATABASE_URL` setting in
`app/config.py` and `.env.example` is dead config. Either remove it or wire
it through `env.py` if you need a separate sync URL — don't add a third
parallel setting.

---

## 5. Code style

### Python (`backend/`)

- **Type hints everywhere.** Use modern syntax: `int | None`, `list[str]`,
  `dict[str, Any]`. `from __future__ import annotations` is fine and used in
  several files.
- **SQLAlchemy 2.0 style** with `Mapped[...]` and `mapped_column`. See
  `app/models/listing.py` for the canonical pattern.
- **Pydantic v2** for schemas. Settings class lives in `app/config.py` and
  uses `pydantic-settings` with field aliases for env var names.
- Module-level `settings = get_settings()` is fine; `get_settings()` is
  `lru_cache`d.
- Logging: `log = logging.getLogger(__name__)`, use `log.exception(...)` in
  `except` blocks where the traceback matters.
- No tests exist yet; if you add them, prefer `pytest` + `pytest-asyncio` and
  put them under `backend/tests/`.

### TypeScript (`frontend/`)

- **TS strict** (see `tsconfig.app.json`). Don't disable strictness to silence
  errors — fix the type.
- React 19 + functional components only. No class components.
- ESLint config in `eslint.config.js`; `npm run lint` must pass.
- Co-locate small components; promote shared primitives into
  `src/components/ui.tsx`.
- Use Tailwind utilities for styling. Avoid inline `style={{ ... }}` unless
  computing a value at runtime.

### General

- **No narration comments.** Don't add comments that just describe what the
  next line does (`// loop over users`, `# return the result`). Comments
  should explain *why*, *trade-offs*, or non-obvious constraints.
- Prefer **editing existing files** over creating new ones. The repo is
  small; sprawl hurts.
- Keep secrets out of commits — `.env` is gitignored, only `.env.example`
  is tracked.

---

## 6. Common task playbooks

### Add a new API endpoint

1. Add a Pydantic schema in `backend/app/schemas/`.
2. Add the route function in the appropriate `backend/app/api/<module>.py`.
   Use `Depends(get_current_user)` for auth, `Depends(require_admin)` for
   admin-only.
3. If it's a brand-new module, register the router in `app/main.py` with
   `prefix="/api"`.
4. Frontend: add a typed wrapper in `frontend/src/lib/<feature>.ts` using
   TanStack Query (`useQuery` / `useMutation`).

### Add a new scrape source

1. Create `backend/scraper/sources/<site>.py` implementing the `Source`
   protocol from `scraper/base.py` (a `name: str` and an
   `async def fetch(self, client) -> list[ScrapedItem]`).
2. Register it in `backend/scraper/sources/__init__.py` by appending to
   `ALL_SOURCES`.
3. The worker auto-schedules every source in `ALL_SOURCES` at
   `SCRAPE_INTERVAL_SECONDS` with jitter — no further wiring needed.
4. Dedupe is by `(source, external_id)` via a Postgres unique constraint +
   `ON CONFLICT DO NOTHING` (see `upsert_items`). Make sure your
   `external_id` is stable per listing.

### Add a database column

1. Edit the model in `backend/app/models/`.
2. If new model: add it to `backend/app/models/__init__.py`.
3. `make migration name="describe change"`.
4. **Review the generated file** in `backend/alembic/versions/` — autogenerate
   is good but not perfect, especially for renames and check constraints.
5. `make migrate`.

### Add a new page

1. Create `frontend/src/pages/<Name>Page.tsx`.
2. Wire a route in `frontend/src/App.tsx`. Wrap in `<ProtectedRoute>` if it
   needs auth.
3. Use existing data hooks in `lib/`; add new ones there if needed.

---

## 7. Things to avoid

- **Don't** add Redis, Celery, or any other broker. The architecture
  deliberately uses Postgres `LISTEN`/`NOTIFY` for cross-process events.
- **Don't** introduce a Python ORM other than SQLAlchemy 2 async, or a sync
  DB driver alongside asyncpg.
- **Don't** add new web frameworks (no Flask, no Express). FastAPI on the
  backend, React/Vite on the frontend.
- **Don't** spin up a separate `node` process supervisor — extend
  `scripts/dev.sh` if you need more dev processes.
- **Don't** write to `.env` from code; it's the user's local secret file.
- **Don't** disable TypeScript strictness, ESLint rules, or Pydantic
  validation to make red squiggles go away.
- **Don't** print or log raw session tokens, password hashes, Cloudflare API
  tokens, or full scraped HTML payloads at INFO level.
- **Don't** run `pip install` in `backend/` — use `uv add <pkg>`.

---

## 8. Quick reference

| Need | File / Command |
|---|---|
| Settings & env vars | `backend/app/config.py`, `.env.example` |
| DB session | `backend/app/database.py` (`SessionLocal`, `get_db`) |
| Auth helpers | `backend/app/deps.py`, `backend/app/security.py` |
| Cross-process events | `backend/app/scraper_events.py` |
| Matcher queue | `backend/app/matcher_jobs.py`, `backend/matcher/worker.py` |
| Models | `backend/app/models/` (register in `__init__.py`) |
| API routes | `backend/app/api/` (mounted with `/api` prefix) |
| Scraper entrypoint | `backend/scraper/worker.py` |
| Scrape sources | `backend/scraper/sources/` |
| Frontend API client | `frontend/src/lib/api.ts` |
| Auth hooks | `frontend/src/lib/auth.ts` |
| Routes / pages | `frontend/src/App.tsx`, `frontend/src/pages/` |
| Dev orchestration | `Makefile`, `scripts/dev.sh` |
| Dev DB | `docker-compose.yml` (host port `5435`), `make db-shell` |
| Prod deploy docs | `deploy/README.md`, `docker-compose.prod.yml` |
| Prod SSH / logs | [§9](#9-production-server-cicd-and-operations) |
| Cloudflare DNS token | Repo `.env` → `CLOUDFLARE_API_TOKEN`; [§9.6](#96-cloudflare-dns-spidersi) |

---

## 9. Production server, CI/CD, and operations

Read this when debugging prod, deploying, or checking scraper health.

### 9.1 Production host

| Item | Value |
|------|--------|
| Provider | Hetzner VPS (Ubuntu 24.04) |
| IP | `46.224.37.205` |
| SSH (admin) | `ssh spider.si` — uses `~/.ssh/config` → `HostName 46.224.37.205`, user `root`, key `~/.ssh/spider-hetzner` |
| SSH (CI / deploy user) | `ssh deploy@46.224.37.205` — key in GitHub secret `DEPLOY_SSH_KEY` |
| App directory | `/opt/spider` (`docker-compose.prod.yml`, `.env`, `deploy/`) |
| Public URL (staging) | **https://new.spider.si** — DNS **A** record must point to `46.224.37.205` |
| Production URL (later) | `https://spider.si` — switch `DOMAIN` / `CORS_ORIGINS` in `/opt/spider/.env` when ready |
| Docker image | `ghcr.io/jakobcvetko/spider-python:latest` (and `:<git-sha>` per deploy) |
| GitHub repo | `jakobcvetko/spider-python` |

**Default seeded admin** (change after first login): `admin@example.com` / `password`.

Server secrets live in `/opt/spider/.env` only (never commit). Includes
`POSTGRES_PASSWORD`, `DOMAIN`, `CORS_ORIGINS`, `SESSION_COOKIE_SECURE=true`.

### 9.2 How production runs

```
Internet → Caddy (:443) → api (uvicorn :8000, serves React from backend/public)
                              ↓
                         Postgres (db)
                              ↑
         worker-lookahead | worker-backfill | worker-matcher
```

- **api** — `uvicorn app.main:app`; static SPA + `/api/*`; `scraper_events` LISTEN for admin WS.
- **worker-lookahead** — `python -m scraper.worker --sources bolha.lookahead`; frontier probe via Bolha iAPI; updates `bolha_ads`, creates `listings`, enqueues matcher.
- **worker-backfill** — `--sources bolha.backfill`; processes `bolha_ads` rows with `status = backfill`.
- **worker-matcher** — `python -m matcher.worker`; LISTEN `matcher_jobs`.
- **db** — Postgres 16, volume `spider_spider_pg_data`.
- **caddy** — TLS for `$DOMAIN` from `.env`.

**Important:** Run migrations **after** deploy, not only on api start. CI runs:
`docker compose … run --rm --no-deps api alembic upgrade head`.
Workers started before migrations will error once (`bolha_scrape_meta does not exist`);
restart workers after migrate if that happens.

### 9.3 CI/CD (GitHub Actions)

Workflow: `.github/workflows/deploy.yml`

**Trigger:** push to `main` or `master`; or manual **Actions → Deploy → Run workflow**.

**Steps:**
1. Build `Dockerfile` (npm build → `backend/public`, `uv sync`).
2. Push to `ghcr.io/jakobcvetko/spider-python:latest` and `:<commit-sha>`.
3. SCP `docker-compose.prod.yml` + `deploy/` → `$DEPLOY_PATH` on server.
4. SSH as `deploy`: `docker login ghcr.io` → `compose pull` → `up -d` → `alembic upgrade head`.

**Required GitHub Actions secrets:**

| Secret | Purpose |
|--------|---------|
| `DEPLOY_HOST` | `46.224.37.205` (prefer IP; `spider.si` DNS may not point at Hetzner yet) |
| `DEPLOY_USER` | `deploy` |
| `DEPLOY_SSH_KEY` | Private key for `deploy@` (PEM) |
| `DEPLOY_PATH` | `/opt/spider` |
| `GHCR_PULL_TOKEN` | PAT with `read:packages` if GHCR image is private |

Ensure `/opt/spider/.env` has `SPIDER_IMAGE=ghcr.io/jakobcvetko/spider-python` (lowercase).
`IMAGE_TAG` is set by CI to the commit SHA on each deploy.

Full bootstrap / first-time setup: [`deploy/README.md`](./deploy/README.md).

### 9.4 Connect and inspect production

**SSH + container status**

```bash
ssh spider.si
cd /opt/spider
docker compose -f docker-compose.prod.yml ps
```

**Health**

```bash
curl -sS https://new.spider.si/api/health
# or via server:
curl -sS -H 'Host: new.spider.si' http://127.0.0.1/api/health
```

**Logs** (follow with `-f`)

```bash
ssh spider.si 'docker compose -f /opt/spider/docker-compose.prod.yml logs -f worker-lookahead'
ssh spider.si 'docker compose -f /opt/spider/docker-compose.prod.yml logs -f worker-backfill'
ssh spider.si 'docker compose -f /opt/spider/docker-compose.prod.yml logs -f worker-matcher'
ssh spider.si 'docker compose -f /opt/spider/docker-compose.prod.yml logs -f api'
ssh spider.si 'docker compose -f /opt/spider/docker-compose.prod.yml logs -f caddy'
```

Useful log filters on server:

```bash
docker compose -f /opt/spider/docker-compose.prod.yml logs worker-lookahead 2>&1 \
  | grep -E 'batch anchor|ERROR|200 OK|listing'
```

**Production database**

```bash
ssh spider.si 'docker exec -it spider-db-1 psql -U spider -d spider'
```

Quick row counts:

```sql
SELECT 'bolha_ads' AS t, COUNT(*) FROM bolha_ads
UNION ALL SELECT 'listings', COUNT(*) FROM listings
UNION ALL SELECT 'scraper_matches', COUNT(*) FROM scraper_matches;
SELECT status, COUNT(*) FROM bolha_ads GROUP BY status;
SELECT last_working_ad_id, last_fetch_high_water FROM bolha_scrape_meta WHERE id = 1;
```

**Manual deploy on server** (if CI is unavailable)

```bash
ssh spider.si
cd /opt/spider
export IMAGE_TAG=latest   # or a specific sha
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d --remove-orphans
docker compose -f docker-compose.prod.yml run --rm --no-deps api alembic upgrade head
```

**Recreate api/caddy after `.env` domain change**

```bash
docker compose -f /opt/spider/docker-compose.prod.yml up -d --force-recreate api caddy
```

### 9.5 What “healthy” scrapers look like

- **lookahead** — logs `bolha lookahead: batch anchor=… high_water=…`; many `404` ahead of frontier is normal; `200 OK` when new ads appear.
- **backfill** — runs on interval; `parsed N candidate items` when fallback queue has work; otherwise idle.
- **matcher** — `matcher worker listening on channel matcher_jobs`; processes jobs when lookahead creates listings.

If workers error on missing tables, run migrations then:
`docker compose -f /opt/spider/docker-compose.prod.yml restart worker-lookahead worker-backfill worker-matcher`.

### 9.6 Cloudflare DNS (`spider.si`)

DNS for **spider.si** is managed in **Cloudflare**. The API token lives in the
repo-root **`.env`** (gitignored) — same file as local `DATABASE_URL`.

**Read the token (agents):** from repo root:

```bash
grep '^CLOUDFLARE_API_TOKEN=' .env | cut -d= -f2-
# or: cat .env   (look for CLOUDFLARE_* lines; do not paste token into chat/commits)
```

Optional in `.env`: `CLOUDFLARE_ZONE_NAME=spider.si` (default zone for API calls).

**Rules:** Never commit the token, put it in tracked files, or print it in logs/chat.
Use env vars in shell one-liners; redact if showing example output.

**Verify token:**

```bash
export CLOUDFLARE_API_TOKEN=$(grep '^CLOUDFLARE_API_TOKEN=' .env | cut -d= -f2-)
curl -sS "https://api.cloudflare.com/client/v4/user/tokens/verify" \
  -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}"
```

**API base:** `https://api.cloudflare.com/client/v4`  
**Auth header:** `Authorization: Bearer <token>`  
**Docs:** https://developers.cloudflare.com/api/

**Production server IP** (A/AAAA targets for Hetzner): `46.224.37.205`

| Task | Method | Path |
|------|--------|------|
| List zones | `GET` | `/zones?name=spider.si` |
| List DNS records | `GET` | `/zones/{zone_id}/dns_records` |
| Filter by name | `GET` | `/zones/{zone_id}/dns_records?name=new.spider.si` |
| Create record | `POST` | `/zones/{zone_id}/dns_records` |
| Update record | `PATCH` | `/zones/{zone_id}/dns_records/{record_id}` |
| Delete record | `DELETE` | `/zones/{zone_id}/dns_records/{record_id}` |

**Typical flow — point staging subdomain at Hetzner:**

```bash
cd /path/to/spider-python
export CLOUDFLARE_API_TOKEN=$(grep '^CLOUDFLARE_API_TOKEN=' .env | cut -d= -f2-)
ZONE_ID=$(curl -sS -G "https://api.cloudflare.com/client/v4/zones" \
  --data-urlencode "name=spider.si" \
  -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
  | jq -r '.result[0].id')

# List records for the zone
curl -sS "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/dns_records" \
  -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" | jq '.result[] | {id,name,type,content,proxied}'

# Create A record for new.spider.si → Hetzner (if missing)
curl -sS -X POST "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/dns_records" \
  -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
  -H "Content-Type: application/json" \
  --data '{"type":"A","name":"new","content":"46.224.37.205","ttl":1,"proxied":false}'
```

Use `"name":"new"` for `new.spider.si` (Cloudflare uses relative name within zone).
For apex `spider.si`, use `"name":"@"`.

**Update existing record** (get `id` from list, then PATCH):

```bash
curl -sS -X PATCH "https://api.cloudflare.com/client/v4/zones/${ZONE_ID}/dns_records/${RECORD_ID}" \
  -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
  -H "Content-Type: application/json" \
  --data '{"content":"46.224.37.205","proxied":false}'
```

**Proxied vs DNS-only:** For Let's Encrypt on the VPS (Caddy), set **`proxied": false`**
(gray cloud). Orange-cloud proxy sends traffic through Cloudflare and can break
direct TLS to Caddy unless you use Cloudflare SSL modes intentionally.

**After DNS change:** Wait for propagation, then Caddy on the server will obtain
certs for `$DOMAIN` in `/opt/spider/.env`. Check: `dig +short new.spider.si A`.

**Common records for this project:**

| Name | Type | Content | Notes |
|------|------|---------|--------|
| `new` | A | `46.224.37.205` | Staging (`new.spider.si`) |
| `@` | A | `46.224.37.205` | When cutting over apex `spider.si` |

Legacy apex may still point elsewhere until you change it — confirm with
`dig +short spider.si A` before switching production traffic.
