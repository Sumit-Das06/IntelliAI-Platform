#!/usr/bin/env bash
# IntelliAI production preflight: everything that must be true BEFORE
# `make prod-up` is allowed to touch Docker. Run from the repository root:
#   ./infra/prod-preflight.sh
# Fails loudly on the first broken requirement; prints PREFLIGHT OK at
# the end and nothing else claims success. No service is started, no
# state is changed — safe to run any number of times.
set -euo pipefail

export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'

# Same knobs as backup.sh: a dry run may point these at a scratch
# project and a generated env file; production uses the defaults.
PROJECT="${INTELLIAI_PROJECT:-intelliai}"
ENV_FILE="${INTELLIAI_ENV_FILE:-.env}"
# M25: the same battery runs against the local production-shaped
# overlay (local-prod.yml) by pointing this at it; default is prod.
OVERLAY="${INTELLIAI_COMPOSE_OVERLAY:-infra/compose/prod.yml}"

fail() { echo "PREFLIGHT FAILED: $*" >&2; exit 1; }
note() { echo "  ok: $*"; }
warn() { echo "  WARN: $*" >&2; }

# ── 1. Docker + compose plugin ──────────────────────────────────────────
command -v docker >/dev/null 2>&1 || fail "docker is not installed (curl -fsSL https://get.docker.com | sh)"
docker info >/dev/null 2>&1 || fail "docker daemon is not reachable (is the service running? are you in the docker group?)"
docker compose version >/dev/null 2>&1 || fail "the docker compose plugin is missing"
note "docker + compose plugin"

# ── 2. env file exists and every required value is set ──────────────────
[ -f "$ENV_FILE" ] || fail "$ENV_FILE not found — cp .env.prod.example .env and fill EVERY value"

# shellcheck disable=SC1090
set -a; . "./$ENV_FILE"; set +a

require() {
  local name="$1" value="${!1:-}"
  [ -n "$value" ] || fail "$name is empty in .env"
}
require DOMAIN
require INTELLIAI_AUTH_KEY_PEPPER
require POSTGRES_PASSWORD
require MINIO_ROOT_PASSWORD
note "required variables present"

# ── 3. Secrets are real, not placeholders ───────────────────────────────
[ "$DOMAIN" != "api.yourdomain.com" ] || fail "DOMAIN is still the example placeholder"
for name in INTELLIAI_AUTH_KEY_PEPPER POSTGRES_PASSWORD MINIO_ROOT_PASSWORD; do
  value="${!name}"
  [ "${#value}" -ge 16 ] || fail "$name is shorter than 16 characters — generate it (openssl rand -hex 16)"
  case "$value" in
    *changeme*|*password*|*secret*|*example*) fail "$name looks like a placeholder, not a generated secret" ;;
  esac
done
note "secrets look generated (length + no placeholder words)"

if [ "$DOMAIN" = "localhost" ]; then
  warn "DOMAIN=localhost — Caddy will self-sign (fine for the local dry run, wrong for production)"
fi

# ── 4. Environment posture (overlay-aware, M25) ─────────────────────────
# The PROD overlay demands the production posture. The LOCAL
# production-shaped overlay demands the OPPOSITE: it serves the pending
# E3 proposal via the staging profile, which the app refuses under
# INTELLIAI_ENV=prod — so prod env there would crash-loop at startup.
if [ "$OVERLAY" = "infra/compose/local-prod.yml" ]; then
  [ "${INTELLIAI_ENV:-}" != "prod" ] \
    || fail "INTELLIAI_ENV must NOT be 'prod' for the local production-shaped stack (the staging registry profile is refused under prod)"
  note "local production-shaped posture (env '${INTELLIAI_ENV:-dev}'; the overlay sets the staging profile itself)"
else
  [ "${INTELLIAI_ENV:-}" = "prod" ] || fail "INTELLIAI_ENV must be 'prod' in .env (found '${INTELLIAI_ENV:-unset}')"
  # The staging registry profile activates unreviewed model routes; the app
  # refuses the combination at startup, but a preflight should say it
  # BEFORE an operator watches a container crash-loop.
  [ -z "${INTELLIAI_REGISTRY_PROFILE:-}" ] || fail "INTELLIAI_REGISTRY_PROFILE must not be set in production (found '${INTELLIAI_REGISTRY_PROFILE}')"
  note "INTELLIAI_ENV=prod, no staging profile"
fi

# ── 4b. The promoted Hindi artifact must be seedable (M26) ──────────────
# The E3 weights are research-provenance and deliberately NOT hosted at
# a resolvable URL: the store serves them from local placement,
# hash-verified at load. A deployment without the bytes would crash-loop
# at startup — say it here instead.
E3_GGUF="models/qwen3-asr-0.6b-hi-ft-e3/v1/Qwen3-ASR-0.6B-Q8_0.gguf"
if [ -f "$E3_GGUF" ]; then
  note "promoted Hindi artifact present for seeding ($E3_GGUF)"
else
  fail "the promoted Hindi artifact is missing: $E3_GGUF — place the E3 GGUFs under models/ (see docs/ops/model-rollout.md), then 'make staging-seed-models' seeds the model volume"
fi

# ── 5. the env file stays private ───────────────────────────────────────
if command -v stat >/dev/null 2>&1; then
  mode="$(stat -c '%a' "$ENV_FILE" 2>/dev/null || echo '')"
  if [ -n "$mode" ] && [ "$mode" != "600" ] && [ "$mode" != "400" ]; then
    warn "$ENV_FILE permissions are $mode — chmod 600 $ENV_FILE on the VPS"
  fi
fi

# ── 6. Compose configuration parses with THESE values ───────────────────
docker compose -p "$PROJECT" --env-file "$ENV_FILE" \
  -f docker-compose.yml -f "$OVERLAY" config -q \
  || fail "docker compose config rejected the production overlay"
note "compose config (base + $OVERLAY)"

# ── 7. Caddyfile syntax, with this DOMAIN ───────────────────────────────
docker run --rm -e "DOMAIN=$DOMAIN" \
  -v "$(pwd)/infra/Caddyfile:/etc/caddy/Caddyfile:ro" \
  caddy:2.10-alpine caddy validate --config /etc/caddy/Caddyfile >/dev/null 2>&1 \
  || fail "caddy validate rejected infra/Caddyfile"
note "Caddyfile validates"

# ── 8. Disk headroom (images + models + database + backups) ─────────────
if command -v df >/dev/null 2>&1; then
  avail_kb="$(df -Pk . | awk 'NR==2 {print $4}')"
  if [ -n "$avail_kb" ] && [ "$avail_kb" -lt $((20 * 1024 * 1024)) ]; then
    warn "less than 20 GB free on this filesystem — images + models + backups need room"
  fi
fi

if [ "$OVERLAY" = "infra/compose/local-prod.yml" ]; then
  echo "PREFLIGHT OK — safe to run: make local-prod-up"
else
  echo "PREFLIGHT OK — safe to run: make prod-build && make prod-up"
fi
