SHELL := /bin/bash
MAKEFLAGS += --no-print-directory

.DEFAULT_GOAL := help
.PHONY: help install dev be fe scraper migrate migration db-up db-down db-shell db-reset stop

help: ## Show this help message
	@printf "\n\033[1mSpider — dev commands\033[0m\n\n"
	@awk 'BEGIN {FS = ":[^#]*## "} /^[a-zA-Z_-]+:[^#]*## / {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@printf "\nExamples:\n  make install        # one-time setup\n  make dev            # run everything\n  make migration name=\"add foo column\"\n\n"

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

be: ## Run backend API only (FastAPI on :8000)
	cd backend && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

fe: ## Run frontend only (Vite on :5173)
	cd frontend && npm run dev -- --host 127.0.0.1 --port 5173

scraper: ## Run scraper worker only (APScheduler)
	cd backend && uv run python -m scraper.worker

dev: db-up migrate ## Run db + backend + frontend (scraper runs separately via `make scraper`)
	@exec bash scripts/dev.sh

stop: db-down ## Stop everything (docker)
