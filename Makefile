# IntelliAI developer interface. `make` with no target lists commands.
# Every routine workflow gets a target here — the Makefile is executable
# documentation and the only interface CI and humans both use.

.DEFAULT_GOAL := help

.PHONY: help up down ps logs clean sync api test migrate migration downgrade build db-ui psql \
        eval-fetch eval speech-eval bench manifest bootstrap-org bootstrap-benchmark-org

help: ## List available commands
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'

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

# ── Evaluation workflows ──────────────────────────────────────
# The documented workflows, executable. Two arguments are deliberately
# NOT defaulted: `hardware` and `out`.
#
# `hardware` is a free string today, and the machine we own is already
# spelled four different ways across committed records. A default here
# would mint a fifth spelling and make it canonical by accident. The
# structured environment identity that replaces it is designed
# (docs/research/hardware-profiles.md) but PROPOSED, not ratified — so
# this Makefile refuses to guess and the operator states the machine.
#
# `out` names a permanent, append-only record. Defaulting it invites
# overwriting evidence, and the record-naming convention is likewise
# still PROPOSED.

CORPUS_STT ?= ml/evaluation/stt/datasets/stt-eval-v2.json
CORPUS_TTS ?= ml/evaluation/tts/corpora/tts-eval-v1.json
MANIFEST   ?= ml/evaluation/manifests/resolution.json

eval-fetch: ## Materialize the STT evaluation dataset into ml/evaluation/data/ (gitignored)
	uv run --package intelliai-evaluation python -m intelliai_evaluation fetch --dataset $(CORPUS_STT)

eval: eval-fetch ## Measure one STT slice: make eval lang=hi engine_version=1.2.1 hardware="..." out=...
	@if [ -z "$(hardware)" ] || [ -z "$(out)" ] || [ -z "$(engine_version)" ]; then \
	  echo "make eval requires hardware=, out= and engine_version=."; \
	  echo; \
	  echo '  make eval lang=en engine_version=<engine x.y.z> \'; \
	  echo '            hardware="<describe THIS machine>" \'; \
	  echo '            out=ml/evaluation/stt/results/$(shell date +%Y-%m-%d)-intelliai-stt-en.json'; \
	  echo; \
	  echo "  No example string is given for hardware on purpose: the machine is"; \
	  echo "  already spelled four ways across committed records and a fifth would"; \
	  echo "  arrive by copy-paste. See the note in the Makefile."; \
	  exit 2; \
	fi
	uv run --package intelliai-evaluation python -m intelliai_evaluation run \
	  --dataset $(CORPUS_STT) --manifest $(MANIFEST) \
	  --url $(or $(url),http://localhost:8001) \
	  --model $(or $(model),intelliai-stt) --language $(or $(lang),en) \
	  --engine $(or $(engine),faster-whisper) --engine-version "$(engine_version)" \
	  --compute $(or $(compute),cpu-int8) --hardware "$(hardware)" \
	  $(if $(benchmark),--benchmark "$(benchmark)",) $(if $(notes),--notes "$(notes)",) \
	  --out $(out)

speech-eval: ## Measure TTS against its corpus via the STT judge: make speech-eval hardware="..." out=...
	@if [ -z "$(hardware)" ] || [ -z "$(out)" ]; then \
	  echo "make speech-eval requires hardware= and out=."; \
	  echo "  needs tts-runtime on :8002 and the judge stt-runtime on :8001"; \
	  exit 2; \
	fi
	uv run --package intelliai-evaluation python -m intelliai_evaluation speech-eval \
	  --corpus $(CORPUS_TTS) \
	  --tts-url $(or $(tts_url),http://localhost:8002) \
	  --stt-url $(or $(stt_url),http://localhost:8001) \
	  --artifact $(or $(artifact),kokoro-82m) --lineage $(or $(lineage),kokoro) \
	  --voice $(or $(voice),reference-alto) --hardware "$(hardware)" \
	  $(if $(baseline),--baseline-name "$(baseline)",) $(if $(notes),--notes "$(notes)",) \
	  --out $(out)

bench: ## STT production ladder + gateway overhead: make bench hardware="..." out=... [key=sk-...]
	@if [ -z "$(hardware)" ] || [ -z "$(out)" ]; then \
	  echo "make bench requires hardware= and out=."; \
	  echo "  without key=, the gateway-overhead phase is SKIPPED and the"; \
	  echo "  record carries no overhead, no p95 and no PRD verdict."; \
	  exit 2; \
	fi
	uv run --package intelliai-evaluation python -m intelliai_evaluation bench \
	  --clip $(or $(clip),ml/evaluation/data/jfk-wav.wav) \
	  --runtime-url $(or $(runtime_url),http://localhost:8001) \
	  --gateway-url $(or $(gateway_url),http://localhost:8000) \
	  --api-key "$(key)" --levels $(or $(levels),1,5,10,20) \
	  --repetitions $(or $(repetitions),3) --hardware "$(hardware)" \
	  $(if $(container),--docker-container "$(container)",) $(if $(notes),--notes "$(notes)",) \
	  --out $(out)

manifest: ## Re-export registry state to ml/evaluation/manifests/ (CI fails if it drifts)
	uv run --package intelliai-api python -m intelliai_api.cli registry-manifest --out $(MANIFEST)

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
	uv run --package intelliai-api python -m intelliai_api.cli bootstrap-org --org-name "$(org)" --owner-email "$(email)" --owner-name "$(name)" --usage-origin $(or $(origin),customer)

# Our own measurement traffic is metered exactly like a customer's and
# rated as none of it. Create this BEFORE the first benchmark session:
# usage events are append-only, so traffic recorded against a customer
# org cannot be reattributed afterwards - it is counted as revenue by
# reconciliation and read as demand by the language report.
bootstrap-benchmark-org: ## Create the benchmark tenant (origin=benchmark, never rated): make bootstrap-benchmark-org email="you@x.com" name="You"
	$(MAKE) bootstrap-org org="$(or $(org),IntelliAI Benchmark)" email="$(email)" name="$(name)" origin=benchmark

db-ui: ## Open a visual database browser (Adminer) at http://localhost:8081
	docker compose --profile tools up -d adminer

psql: ## Open a psql shell inside the Postgres container
	docker compose exec postgres psql -U intelliai -d intelliai
