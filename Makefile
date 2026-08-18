# IntelliAI developer interface. `make` with no target lists commands.
# Every routine workflow gets a target here — the Makefile is executable
# documentation and the only interface CI and humans both use.

.DEFAULT_GOAL := help

.PHONY: help up down ps logs clean sync api test migrate migration downgrade build db-ui psql \
        eval-fetch eval speech-eval bench manifest bootstrap-org bootstrap-benchmark-org \
        keyboard-apk keyboard-test \
        local-prod-check local-prod-build local-prod-up local-prod-migrate \
        local-prod-health local-prod-smoke local-prod-down \
        prod-check prod-config-check prod-build prod-up prod-migrate prod-health prod-smoke \
        prod-backup prod-restore-check prod-down

help: ## List available commands
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'

up: ## Start the platform, STT-only (API + STT + Postgres + Redis + MinIO); TTS via make up-tts
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
	uv run --package intelliai-datasets pytest ml/datasets/tests -q
	uv run --package intelliai-evaluation pytest ml/evaluation/tests -q
	uv run --package intelliai-training pytest ml/training/tests -q
	uv run --package intelliai-runtime-contract pytest packages/runtime-contract/tests -q
	uv run --package intelliai-runtime-core pytest packages/runtime-core/tests -q
	uv run --package intelliai-stt-runtime pytest services/stt-runtime/tests -q
	uv run --package intelliai-tts-runtime pytest services/tts-runtime/tests -q

stt: ## Run the STT runtime locally with hot reload (port 8001)
	uv run --package intelliai-stt-runtime uvicorn --factory intelliai_stt_runtime.main:create_app --reload --port 8001

# ── Research hosting ──────────────────────────────────────────
# A challenger runs in its OWN process on its OWN port, declared by
# artifact identity. The gateway has no deployment entry for it, the
# registry has no route to it, and the only thing that resolves it is
# ml/evaluation/manifests/research.json. Weights are downloaded and
# hash-verified on first start; identity comes from the pins, never from
# this declaration.
research-stt: ## Host a challenger for research: make research-stt artifact=whisper-base [port=8003]
	@if [ -z "$(artifact)" ]; then \
	  echo "make research-stt requires artifact= (a REGISTERED checkpoint, e.g. whisper-base)."; \
	  echo "  Admitting a new checkpoint is a pinned entry in the engine's"; \
	  echo "  artifact table (engines/whisper.py), never a declaration."; \
	  exit 2; \
	fi
	INTELLIAI_STT_SLOTS="whisper:$(artifact)" uv run --package intelliai-stt-runtime \
	  uvicorn --factory intelliai_stt_runtime.main:create_app --port $(or $(port),8003)

# ── Evaluation workflows ──────────────────────────────────────
# The documented workflows, executable.
#
# `hardware`, `compute` and `engine_version` are GONE from `make eval`.
# The runtime reports its own build, decode configuration and machine at
# /info, so asking an operator for them was asking for facts the system
# already holds — which is how one machine came to be spelled four
# different ways across committed records. Nobody spells it now.
#
# `out` is still not defaulted: it names a permanent, append-only record,
# and defaulting it invites overwriting evidence.
#
# The TTS workflows still take `hardware` because the synthesis runtime
# does not yet describe itself; that is symmetric work, not this
# milestone's.

CORPUS_STT ?= ml/evaluation/stt/datasets/stt-eval-v2.json
CORPUS_TTS ?= ml/evaluation/tts/corpora/tts-eval-v1.json
MANIFEST   ?= ml/evaluation/manifests/resolution.json

eval-fetch: ## Materialize the STT evaluation dataset into ml/evaluation/data/ (gitignored)
	uv run --package intelliai-evaluation python -m intelliai_evaluation fetch --dataset $(CORPUS_STT)

eval: eval-fetch ## Measure one STT slice: make eval lang=hi out=...
	@if [ -z "$(out)" ]; then \
	  echo "make eval requires out=."; \
	  echo; \
	  echo '  make eval lang=en \'; \
	  echo '            out=ml/evaluation/stt/results/$(shell date +%Y-%m-%d)-intelliai-stt-en.json'; \
	  echo; \
	  echo "  The build, the decode configuration and the machine are read from the"; \
	  echo "  runtime's /info - there is no flag for any of them, on purpose."; \
	  exit 2; \
	fi
	uv run --package intelliai-evaluation python -m intelliai_evaluation run \
	  --dataset $(CORPUS_STT) --manifest $(MANIFEST) \
	  --url $(or $(url),http://localhost:8001) \
	  --model $(or $(model),intelliai-stt) --language $(or $(lang),en) \
	  --engine $(or $(engine),faster-whisper) \
	  $(if $(benchmark),--benchmark "$(benchmark)",) $(if $(session),--session "$(session)",) \
	  $(if $(notes),--notes "$(notes)",) \
	  --out $(out)

speech-eval: ## Measure TTS via the STT judge (needs make up-tts first): make speech-eval hardware="..." out=...
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

bench: ## STT production ladder + gateway overhead: make bench lang=en hardware="..." out=... [key=sk-...]
	@if [ -z "$(hardware)" ] || [ -z "$(out)" ] || [ -z "$(lang)" ]; then \
	  echo "make bench requires lang=, hardware= and out=."; \
	  echo "  lang= is required because a ladder that declares no language measures"; \
	  echo "  auto-detection, while the quality pass measures explicit declaration -"; \
	  echo "  and the two halves of a session must describe the same system."; \
	  echo "  without key=, the gateway-overhead phase is SKIPPED and the"; \
	  echo "  record carries no overhead, no p95 and no PRD verdict."; \
	  exit 2; \
	fi
	uv run --package intelliai-evaluation python -m intelliai_evaluation bench \
	  --clip $(or $(clip),ml/evaluation/data/jfk-wav.wav) \
	  --runtime-url $(or $(runtime_url),http://localhost:8001) \
	  --gateway-url $(or $(gateway_url),http://localhost:8000) \
	  --api-key "$(key)" --levels $(or $(levels),1,5,10,20) \
	  --repetitions $(or $(repetitions),3) --hardware "$(hardware)" --language "$(lang)" \
	  $(if $(container),--docker-container "$(container)",) $(if $(notes),--notes "$(notes)",) \
	  --out $(out)

manifest: ## Re-export registry state to ml/evaluation/manifests/ (CI fails if it drifts)
	uv run --package intelliai-api python -m intelliai_api.cli registry-manifest --out $(MANIFEST)

# A session executes a REVIEWED spec. Idleness is asserted by a named
# operator at execution time (procedure P-9) - never assumed, never
# stored in the spec, because a plan cannot know the machine will be
# idle when it finally runs.
session: ## Execute one campaign session: make session spec=... idle_by="Your Name"
	@if [ -z "$(spec)" ] || [ -z "$(idle_by)" ]; then \
	  echo "make session requires spec= and idle_by=."; \
	  echo '  make session spec=ml/evaluation/stt/sessions/specs/<file>.json idle_by="Your Name"'; \
	  exit 2; \
	fi
	uv run --package intelliai-evaluation python -m intelliai_evaluation session \
	  --spec $(spec) --assert-idle-by "$(idle_by)"

# ── Android keyboard (apps/keyboard-android) ─────────────────────────
# A self-contained Gradle project — not a uv workspace member. Needs
# JDK 17 and an Android SDK (local.properties or ANDROID_HOME).
keyboard-apk: ## Build the IntelliAI Keyboard debug APK
	cd apps/keyboard-android && ./gradlew assembleDebug
	@echo "APK: apps/keyboard-android/app/build/outputs/apk/debug/app-debug.apk"

keyboard-test: ## Run the keyboard's unit tests and lint
	cd apps/keyboard-android && ./gradlew test lintDebug

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

# Consent is opt-in by law: nothing is stored for model improvement until
# an operator records the tenant's explicit grant, and revocation stops
# collection immediately. ref= names the signed document the grant rests
# on (e.g. ref="cohort-2026-08-consent-v1").
grant-consent: ## Record a tenant's data-collection opt-in: make grant-consent org=org_... ref="doc"
	uv run --package intelliai-api python -m intelliai_api.cli grant-consent --org "$(org)" $(if $(ref),--reference "$(ref)",)

revoke-consent: ## Withdraw a tenant's data-collection consent: make revoke-consent org=org_...
	uv run --package intelliai-api python -m intelliai_api.cli revoke-consent --org "$(org)"

# Erasure is the right to be forgotten, made executable (docs/DATA_GOVERNANCE.md):
# objects first, rows second, usage ledger retained by law. Irreversible.
erase-sample: ## Permanently erase one speech sample: make erase-sample org=org_... sample=smp_...
	uv run --package intelliai-api python -m intelliai_api.cli erase-sample --org "$(org)" --sample "$(sample)"

erase-user-data: ## Erase every sample one identity contributed: make erase-user-data org=org_... user=key_...
	uv run --package intelliai-api python -m intelliai_api.cli erase-user-data --org "$(org)" --user-identifier "$(user)"

erase-org: ## Erase a tenant's data (ledger kept, org row anonymized): make erase-org org=org_...
	uv run --package intelliai-api python -m intelliai_api.cli erase-org --org "$(org)" --yes

up-tts: ## Also start the TTS runtime (V1 is STT-only by default)
	docker compose --profile tts up -d

# ── Local staging: the Hindi→Qwen canary shape, on THIS machine only ──
# (docs/ops/local-staging.md). Explicit overlay, never applied by any
# other target; production posture is unaffected by construction.
staging-up: ## Start the LOCAL staging stack (hi→Qwen, everything else→Whisper); builds images
	docker compose -f docker-compose.yml -f infra/compose/local-staging.yml up -d --build

staging-down: ## Stop the local staging stack (data volumes preserved)
	docker compose -f docker-compose.yml -f infra/compose/local-staging.yml down

staging-seed-models: ## Copy locally-present Qwen GGUFs into the model volume (the E3 candidate is research-only and CANNOT be downloaded)
	docker run --rm -v intelliai_modelcache:/models \
	  -v "$(CURDIR)/models/qwen3-asr-0.6b:/src-base:ro" \
	  -v "$(CURDIR)/models/qwen3-asr-0.6b-hi-ft-e3:/src-e3:ro" \
	  alpine sh -c "mkdir -p /models/qwen3-asr-0.6b /models/qwen3-asr-0.6b-hi-ft-e3 \
	  && cp -r /src-base/v1 /models/qwen3-asr-0.6b/ \
	  && cp -r /src-e3/v1 /models/qwen3-asr-0.6b-hi-ft-e3/ \
	  && ls -la /models/qwen3-asr-0.6b/v1 /models/qwen3-asr-0.6b-hi-ft-e3/v1"

# ── Local production-shaped stack (M25; see docs/ops/local-tunnel.md) ─
# The EXACT production architecture (base + Caddy edge) with the ONE
# staging difference: hi -> qwen3-asr-0.6b-hi-ft-e3 via the staging
# registry profile. Never referenced by any prod-* target; the settings
# layer refuses the staging profile under INTELLIAI_ENV=prod.

LOCAL_PROD_OVERLAY := infra/compose/local-prod.yml
LOCAL_PROD := docker compose -f docker-compose.yml -f $(LOCAL_PROD_OVERLAY)

local-prod-check: ## Preflight the local production-shaped stack (same battery as prod-check)
	INTELLIAI_COMPOSE_OVERLAY=$(LOCAL_PROD_OVERLAY) bash infra/prod-preflight.sh

local-prod-build: ## Build the local production-shaped images (same Dockerfiles as prod)
	$(LOCAL_PROD) build

local-prod-up: staging-seed-models ## Seed models + start the local production-shaped stack
	$(LOCAL_PROD) up -d --build

local-prod-migrate: ## Apply migrations inside the local production-shaped stack
	$(LOCAL_PROD) run --rm --no-deps api alembic -c apps/api/alembic.ini upgrade head

local-prod-health: ## Health read: gateway live/ready + runtime slot-truthful ready
	@curl -fsS --max-time 5 http://127.0.0.1:8000/health/live && echo " <- /health/live"
	@curl -fsS --max-time 10 http://127.0.0.1:8000/health/ready && echo " <- /health/ready"
	@curl -fsS --max-time 10 http://127.0.0.1:8001/health/ready && echo " <- stt-runtime /health/ready"

local-prod-smoke: ## Full smoke against the local production-shaped stack (same battery as prod-smoke)
	INTELLIAI_COMPOSE_OVERLAY=$(LOCAL_PROD_OVERLAY) bash infra/prod-smoke.sh

local-prod-down: ## Stop the local production-shaped stack (volumes are kept)
	$(LOCAL_PROD) down

# ── Production (see docs/ops/deployment.md) ───────────────────────────
# The deployment sequence, in call order:
#   prod-check → prod-build → prod-up → prod-migrate → prod-health → prod-smoke
# Every target is idempotent; nothing here reaches beyond this machine.

prod-check: ## Preflight: docker, .env completeness, secrets, compose config, Caddyfile — BEFORE touching services
	bash infra/prod-preflight.sh

prod-config-check: prod-check ## Alias for prod-check (configuration validation only)

prod-build: ## Build the production images without starting anything
	docker compose -f docker-compose.yml -f infra/compose/prod.yml build

prod-up: ## Deploy/refresh the production stack (base + prod overlay, builds images)
	docker compose -f docker-compose.yml -f infra/compose/prod.yml up -d --build

# Migrations refuse to run without a fresh backup (<24 h): the runbook's
# backup-before-migration rule, made mechanical. force=1 overrides for
# the very first deploy of an empty database.
prod-migrate: ## Apply database migrations (requires a <24h backup; first deploy: force=1)
	@if [ -z "$(force)" ] && ! find backups -name 'pg-*.sql.gz' -mtime -1 2>/dev/null | grep -q .; then \
	  echo "REFUSED: no Postgres backup newer than 24h in backups/."; \
	  echo "  Run 'make prod-backup' first (or force=1 for a first deploy of an empty database)."; \
	  exit 2; \
	fi
	docker compose -f docker-compose.yml -f infra/compose/prod.yml run --rm --no-deps api \
	  alembic -c apps/api/alembic.ini upgrade head

prod-health: ## Quick health read: gateway live/ready + runtime ready (running stack)
	@curl -fsS --max-time 5 http://127.0.0.1:8000/health/live && echo " <- /health/live"
	@curl -fsS --max-time 10 http://127.0.0.1:8000/health/ready && echo " <- /health/ready"
	@curl -fsS --max-time 10 http://127.0.0.1:8001/health/ready && echo " <- stt-runtime /health/ready"

prod-smoke: ## Full smoke: services, health, migrations-at-head, auth refusal, edge headers, port exposure
	bash infra/prod-smoke.sh

prod-backup: ## Production backup (same as `make backup`: pg dump + volume tar + object mirror)
	bash infra/backup.sh
	bash infra/backup-objects.sh

prod-restore-check: ## Prove the newest pg backup restores (disposable container; live data untouched)
	bash infra/restore-check.sh

prod-down: ## Stop the production stack (volumes are kept)
	docker compose -f docker-compose.yml -f infra/compose/prod.yml down

backup: ## Full backup: pg dump + volume tar + object-level mirror (docs/ops/backup.md)
	bash infra/backup.sh
	bash infra/backup-objects.sh

backup-objects: ## Object-level bucket snapshot only (the PRIMARY object backup)
	bash infra/backup-objects.sh

restore-objects: ## Mirror a snapshot into an explicit target: make restore-objects snapshot=backups/objects-... (target via INTELLIAI_RESTORE_S3_* env)
	bash infra/restore-objects.sh "$(snapshot)"

db-ui: ## Open a visual database browser (Adminer) at http://localhost:8081
	docker compose --profile tools up -d adminer

psql: ## Open a psql shell inside the Postgres container
	docker compose exec postgres psql -U intelliai -d intelliai
