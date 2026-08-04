# IntelliAI developer interface. `make` with no target lists commands.
# Every routine workflow gets a target here — the Makefile is executable
# documentation and the only interface CI and humans both use.

.DEFAULT_GOAL := help

.PHONY: help up down ps logs clean sync api test migrate migration downgrade build db-ui psql eval-fetch

help: ## List available commands
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

up: ## Start the full platform (API + Postgres + Redis + MinIO)
	docker compose up -d

build: ## Rebuild the API image (after dependency changes)
	docker compose build api

down: ## Stop all services (data volumes preserved)
	docker compose down

ps: ## Show service status and health
	docker compose ps

logs: ## Tail logs from all services
	docker compose logs -f --tail=100

clean: ## Stop services and DELETE all data volumes
	docker compose down -v

sync: ## Install/sync all Python dependencies (uv workspace)
	uv sync --all-packages

api: ## Run the API gateway locally with hot reload
	uv run --package intelliai-api uvicorn --factory intelliai_api.main:create_app --reload --port 8000

test: ## Run the Python test suite (all workspace packages)
	uv run --package intelliai-api pytest apps/api/tests -q
	uv run --package intelliai-evaluation pytest ml/evaluation/tests -q
	uv run --package intelliai-runtime-contract pytest packages/runtime-contract/tests -q
	uv run --package intelliai-runtime-core pytest packages/runtime-core/tests -q
	uv run --package intelliai-stt-runtime pytest services/stt-runtime/tests -q
	uv run --package intelliai-tts-runtime pytest services/tts-runtime/tests -q

stt: ## Run the STT runtime locally with hot reload (port 8001)
	uv run --package intelliai-stt-runtime uvicorn --factory intelliai_stt_runtime.main:create_app --reload --port 8001

eval-fetch: ## Materialize the STT evaluation dataset into ml/evaluation/data/
	uv run --package intelliai-evaluation python -m intelliai_evaluation fetch --dataset ml/evaluation/stt/datasets/stt-eval-v1.json

migrate: ## Apply database migrations to head
	uv run --package intelliai-api alembic -c apps/api/alembic.ini upgrade head

migration: ## Create a migration: make migration m="add users table"
	uv run --package intelliai-api alembic -c apps/api/alembic.ini revision --autogenerate -m "$(m)"

downgrade: ## Revert the most recent migration
	uv run --package intelliai-api alembic -c apps/api/alembic.ini downgrade -1

lint: ## Check lint + formatting (read-only)
	uv run ruff check .
	uv run ruff format --check .

format: ## Auto-fix lint violations and reformat
	uv run ruff check --fix .
	uv run ruff format .

typecheck: ## Run mypy strict type checking
	uv run mypy

check: ## The full local gate: lint + types + tests
	$(MAKE) lint
	$(MAKE) typecheck
	$(MAKE) test

hooks: ## Install git hooks (run once per clone)
	uv run pre-commit install --hook-type pre-commit --hook-type commit-msg

bootstrap-org: ## Create org + owner + first API key: make bootstrap-org org="Acme" email="you@x.com" name="You"
	uv run --package intelliai-api python -m intelliai_api.cli bootstrap-org --org-name "$(org)" --owner-email "$(email)" --owner-name "$(name)"

db-ui: ## Open a visual database browser (Adminer) at http://localhost:8081
	docker compose --profile tools up -d adminer

psql: ## Open a psql shell inside the Postgres container
	docker compose exec postgres psql -U intelliai -d intelliai
