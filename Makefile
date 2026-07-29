# IntelliAI developer interface. `make` with no target lists commands.
# Every routine workflow gets a target here — the Makefile is executable
# documentation and the only interface CI and humans both use.

.DEFAULT_GOAL := help

.PHONY: help up down ps logs clean sync api test

help: ## List available commands
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

up: ## Start dev infrastructure (Postgres, Redis, MinIO)
	docker compose up -d

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

test: ## Run the Python test suite
	uv run --package intelliai-api pytest apps/api/tests -q
