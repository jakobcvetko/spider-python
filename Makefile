SHELL := /bin/bash
MAKEFLAGS += --no-print-directory

.DEFAULT_GOAL := help
.PHONY: help install dev be fe migrate migration db-up db-down db-shell db-reset stop \
	bolha\:lookahead bolha\:backfill bolha\:scout avtonet avtonet\:lookahead avtonet\:scout matcher \
	firecrawl-up firecrawl-down firecrawl-logs firecrawl-test

help: ## Show this help message
	@printf "\n\033[1mSpider — dev commands\033[0m\n\n"
	@awk 'BEGIN {FS = ":[^#]*## "} /^[a-zA-Z_-]+:[^#]*## / {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@printf "  \033[36m%-12s\033[0m %s\n" "bolha:lookahead" "Scout anchor, then run Bolha lookahead loop"
	@printf "  \033[36m%-12s\033[0m %s\n" "bolha:backfill" "Run Bolha backfill scraper worker only"
	@printf "  \033[36m%-12s\033[0m %s\n" "bolha:scout" "Find Bolha last_working id (one-shot) and exit"
	@printf "  \033[36m%-12s\033[0m %s\n" "avtonet" "Probe avto.net detail IDs (blocking test)"
	@printf "  \033[36m%-12s\033[0m %s\n" "avtonet:lookahead" "Scout anchor, then run avto.net lookahead loop"
	@printf "  \033[36m%-12s\033[0m %s\n" "avtonet:scout" "Find avto.net last_working id (one-shot) and exit"
	@printf "  \033[36m%-12s\033[0m %s\n" "matcher" "Run matcher worker (listing -> scraper matches)"
	@printf "  \033[36m%-12s\033[0m %s\n" "firecrawl-up" "Start self-hosted Firecrawl (Docker, :3002)"
	@printf "  \033[36m%-12s\033[0m %s\n" "firecrawl-down" "Stop self-hosted Firecrawl"
	@printf "  \033[36m%-12s\033[0m %s\n" "firecrawl-test" "Probe 2 avto.net ads via local Firecrawl"
	@printf "\nExamples:\n  make install        # one-time setup\n  make dev            # run everything\n  make bolha:lookahead\n  make migration name=\"add foo column\"\n\n"

install: ## Install all dependencies (backend + frontend)
	@echo "==> Installing backend dependencies (uv)..."
	cd backend && uv sync
	@echo "==> Installing frontend dependencies (npm)..."
	cd frontend && npm install
	@echo "==> Done. Next: make dev"

db-up: ## Start Postgres in docker (waits for healthy)
	@docker compose up -d --wait

db-down: ## Stop Postgres
	@docker compose down

db-shell: ## Open psql shell on the dev database
	docker exec -it spider_pg psql -U spider -d spider

db-reset: ## DROP database volume and re-apply migrations (destructive!)
	@docker compose down -v
	@docker compose up -d --wait
	cd backend && uv run alembic upgrade head

migrate: db-up ## Apply pending database migrations
	@echo "==> Running alembic upgrade head..."
	cd backend && uv run alembic upgrade head

migration: ## Create new migration. Usage: make migration name="add x"
	@if [ -z "$(name)" ]; then echo 'Usage: make migration name="describe change"' >&2; exit 1; fi
	cd backend && uv run alembic revision --autogenerate -m "$(name)"

be: ## Run backend API only (FastAPI on :4000)
	cd backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 4000

fe: ## Run frontend only (Vite on :3000)
	cd frontend && npm run dev -- --host 127.0.0.1 --port 3000

bolha\:lookahead: ## Scout anchor, then run Bolha lookahead loop (long-running)
	cd backend && uv run python -m scraper.worker --sources bolha.lookahead

bolha\:backfill: ## Run Bolha backfill scraper worker only
	cd backend && uv run python -m scraper.worker --sources bolha.backfill

bolha\:scout: ## Find Bolha last_working id via gallop+binary search (exits when done)
	cd backend && uv run python -m scraper.worker --sources bolha.scout

avtonet: ## Probe avto.net detail IDs (blocking test; default anchor 22421224)
	cd backend && uv run python -m scraper.sources.avto_net_lookahead --start-id 22421224 --count 5

avtonet\:lookahead: ## Scout anchor, then run avto.net lookahead loop
	cd backend && uv run python -m scraper.worker --sources avto.net.lookahead

avtonet\:scout: ## Find avto.net last_working id via gallop+binary search (exits when done)
	cd backend && uv run python -m scraper.worker --sources avto.net.scout

matcher: ## Run matcher worker (processes listing match jobs via NOTIFY)
	cd backend && uv run python -m matcher.worker

firecrawl-up: ## Start self-hosted Firecrawl (API on http://127.0.0.1:3002)
	@echo "==> Pulling Firecrawl images (first run may take several minutes)..."
	docker compose -f docker-compose.firecrawl.yml pull
	docker compose -f docker-compose.firecrawl.yml up -d
	@echo "==> Waiting for API on :3002 (can take 1–3 min on first start)..."
	@for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30; do \
		curl -sf -o /dev/null -X POST http://127.0.0.1:3002/v2/scrape \
			-H 'Content-Type: application/json' \
			-d '{"url":"https://example.com","formats":["html"]}' && { \
			echo "==> Firecrawl ready at http://127.0.0.1:3002"; exit 0; }; \
		echo "  still starting ($$i/30)..."; sleep 10; \
	done; \
	echo "ERROR: Firecrawl API did not become ready — run: make firecrawl-logs" >&2; exit 1

firecrawl-down: ## Stop self-hosted Firecrawl
	docker compose -f docker-compose.firecrawl.yml down

firecrawl-logs: ## Follow self-hosted Firecrawl API logs
	docker compose -f docker-compose.firecrawl.yml logs -f firecrawl-api

firecrawl-test: ## Probe 2 avto.net ads (needs firecrawl-up + FIRECRAWL_API_URL in .env)
	cd backend && uv run python -m scraper.sources.avto_net_lookahead --start-id 22421224 --count 2 --no-persist

dev: db-up migrate ## Run db + backend + frontend (scrapers: make bolha:lookahead / bolha:backfill)
	@exec bash scripts/dev.sh

stop: db-down ## Stop everything (docker)
