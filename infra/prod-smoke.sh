#!/usr/bin/env bash
# IntelliAI production smoke test: everything that must be true AFTER
# `make prod-up` before the deployment may be called healthy. Run from
# the repository root on the deployment host:
#   ./infra/prod-smoke.sh
# Read-only against the running stack (plus one optional transcription
# if INTELLIAI_SMOKE_API_KEY is exported). Fails loudly on the first
# broken requirement.
set -euo pipefail

export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'

# Same knobs as backup.sh: a dry run may point these at a scratch
# project and a generated env file; production uses the defaults.
PROJECT="${INTELLIAI_PROJECT:-intelliai}"
ENV_FILE="${INTELLIAI_ENV_FILE:-.env}"
# M25: the same battery runs against the local production-shaped
# overlay (local-prod.yml) by pointing this at it; default is prod.
OVERLAY="${INTELLIAI_COMPOSE_OVERLAY:-infra/compose/prod.yml}"

COMPOSE="docker compose -p $PROJECT --env-file $ENV_FILE -f docker-compose.yml -f $OVERLAY"
fail() { echo "SMOKE FAILED: $*" >&2; exit 1; }
note() { echo "  ok: $*"; }
warn() { echo "  WARN: $*" >&2; }

# curl's discard target: the native Windows curl in a Git Bash dry run
# cannot open a literal /dev/null; the VPS always can.
DEVNULL="/dev/null"
case "$(uname -s 2>/dev/null)" in MINGW*|MSYS*) DEVNULL="NUL" ;; esac

[ -f "$ENV_FILE" ] || fail "$ENV_FILE not found — run from the repository root"
# shellcheck disable=SC1090
set -a; . "./$ENV_FILE"; set +a

# ── 1. Every expected service is up ─────────────────────────────────────
for service in caddy api stt-runtime postgres redis minio; do
  state="$($COMPOSE ps --format '{{.Service}} {{.State}}' 2>/dev/null | awk -v s="$service" '$1==s {print $2}')"
  [ "$state" = "running" ] || fail "service '$service' is not running (state: '${state:-absent}')"
done
note "all six services running"

# ── 2. Container healthchecks are green ─────────────────────────────────
for service in api stt-runtime postgres redis minio; do
  health="$($COMPOSE ps --format '{{.Service}} {{.Health}}' 2>/dev/null | awk -v s="$service" '$1==s {print $2}')"
  [ "$health" = "healthy" ] || fail "service '$service' healthcheck is '$health', not healthy"
done
note "container healthchecks healthy"

# ── 3. Gateway liveness + readiness (host-local bind) ───────────────────
curl -fsS --max-time 5 http://127.0.0.1:8000/health/live >/dev/null \
  || fail "gateway /health/live did not answer on 127.0.0.1:8000"
ready="$(curl -fsS --max-time 10 http://127.0.0.1:8000/health/ready || true)"
echo "$ready" | grep -q '"status"[[:space:]]*:[[:space:]]*"healthy"' \
  || fail "gateway /health/ready is not 'healthy': $ready"
note "gateway live + ready (healthy)"

# ── 4. Runtime readiness is slot-truthful and ready ─────────────────────
runtime_ready="$(curl -fsS --max-time 10 http://127.0.0.1:8001/health/ready || true)"
echo "$runtime_ready" | grep -q '"status"[[:space:]]*:[[:space:]]*"ready"' \
  || fail "stt-runtime /health/ready is not 'ready': $runtime_ready"
note "stt-runtime ready (artifacts hash-verified at load — ready IS the artifact check)"

# ── 4b. Punctuation stage posture matches the declared config (M31) ─────
# The declared posture lives in the OVERLAY first (local-prod enables the
# stage in compose), the environment second — read both, overlay wins.
PUNCT_ENABLED="${INTELLIAI_STT_PUNCTUATION_ENABLED:-false}"
if grep -q 'INTELLIAI_STT_PUNCTUATION_ENABLED: "true"' "$OVERLAY" 2>/dev/null; then
  PUNCT_ENABLED=true
elif grep -q 'INTELLIAI_STT_PUNCTUATION_ENABLED: "false"' "$OVERLAY" 2>/dev/null; then
  PUNCT_ENABLED=false
fi
if [ "$PUNCT_ENABLED" = "true" ]; then
  echo "$runtime_ready" | grep -q '"punctuation"[[:space:]]*:[[:space:]]*"ready"'     || fail "punctuation is ENABLED but the runtime does not report it ready: $runtime_ready"
  note "punctuation stage ready"
else
  echo "$runtime_ready" | grep -q '"punctuation"[[:space:]]*:[[:space:]]*"ready"'     && fail "punctuation reports ready but the deployment declares it OFF"     || note "punctuation stage disabled (as declared)"
fi

# ── 5. Migrations are at head ───────────────────────────────────────────
current="$($COMPOSE run --rm --no-deps api alembic -c apps/api/alembic.ini current 2>/dev/null | grep -oE '^[0-9a-f]+' | head -1 || true)"
head_rev="$($COMPOSE run --rm --no-deps api alembic -c apps/api/alembic.ini heads 2>/dev/null | grep -oE '^[0-9a-f]+' | head -1 || true)"
[ -n "$current" ] || fail "could not read the current migration revision (did prod-migrate run?)"
[ "$current" = "$head_rev" ] || fail "database is at $current but head is $head_rev — run make prod-migrate"
note "migrations at head ($current)"

# ── 6. Authentication is enforced ───────────────────────────────────────
status="$(curl -s -o "$DEVNULL" -w '%{http_code}' --max-time 10 -X POST http://127.0.0.1:8000/v1/audio/transcriptions)"
[ "$status" = "401" ] || fail "unauthenticated transcription returned $status, expected 401"
note "unauthenticated request refused (401)"

# ── 7. Edge: HTTPS answers, HTTP redirects, headers ride ────────────────
# With DOMAIN=localhost Caddy self-signs, so -k; with a real domain the
# chain must also verify (second, strict call).
edge="https://${DOMAIN}"
headers="$(curl -ksS -o "$DEVNULL" -D - --max-time 10 "$edge/health/live" || true)"
echo "$headers" | grep -qi '^HTTP/.* 200' || fail "edge $edge/health/live did not answer 200 through Caddy"
echo "$headers" | grep -qi 'strict-transport-security' || fail "HSTS header missing at the edge"
echo "$headers" | grep -qi 'x-content-type-options:[[:space:]]*nosniff' || fail "nosniff header missing at the edge"
echo "$headers" | grep -qi '^server:' && fail "the edge leaks a Server header"
redirect="$(curl -s -o "$DEVNULL" -w '%{http_code}' --max-time 10 "http://${DOMAIN}/health/live" || true)"
case "$redirect" in
  301|302|308) note "edge: HTTPS 200 + headers, HTTP redirects ($redirect)" ;;
  *) fail "HTTP did not redirect to HTTPS (got '$redirect')" ;;
esac
if [ "$DOMAIN" != "localhost" ]; then
  curl -fsS -o "$DEVNULL" --max-time 10 "$edge/health/live" \
    || fail "certificate for $DOMAIN does not verify (Let's Encrypt not issued yet?)"
  note "certificate verifies for $DOMAIN"
fi

# ── 8. Nothing internal listens beyond loopback ─────────────────────────
# Every published port except Caddy's 80/443 must be host-loopback.
exposed="$($COMPOSE ps --format '{{.Service}} {{.Publishers}}' 2>/dev/null | grep -v '^caddy ' | grep -oE '0\.0\.0\.0:[0-9]+' | grep -vE ':(80|443)$' || true)"
[ -z "$exposed" ] || fail "internal service published beyond loopback: $exposed"
note "internal ports loopback-only; Caddy alone faces the internet"

# ── 9. Optional: one real transcription through the edge ────────────────
if [ -n "${INTELLIAI_SMOKE_API_KEY:-}" ]; then
  # python3 on the VPS. A Windows dry run may carry only `python`, `py`,
  # or a Store SHIM that pretends to exist — so probe by RUNNING, not by
  # PATH presence.
  PYTHON=""
  for candidate in python3 python py "uv run python"; do
    if $candidate -c "pass" >/dev/null 2>&1; then PYTHON="$candidate"; break; fi
  done
  [ -n "$PYTHON" ] || fail "no working python available to generate the smoke clip"
  # A cwd-relative scratch file: mktemp's /tmp is a Git-Bash fiction a
  # native Windows python cannot open, and the VPS does not care.
  wav="./smoke-clip-$$.wav"
  trap 'rm -f "$wav"' EXIT
  # One second of silence, canonical PCM — no source audio required.
  $PYTHON - "$wav" <<'PY'
import struct, sys
frames = b"\x00\x00" * 16000
header = (b"RIFF" + struct.pack("<I", 36 + len(frames)) + b"WAVEfmt " +
          struct.pack("<IHHIIHH", 16, 1, 1, 16000, 32000, 2, 16) +
          b"data" + struct.pack("<I", len(frames)))
open(sys.argv[1], "wb").write(header + frames)
PY
  code="$(curl -ks -o "$DEVNULL" -w '%{http_code}' --max-time 60 \
    -H "Authorization: Bearer $INTELLIAI_SMOKE_API_KEY" \
    -F "file=@$wav;type=audio/wav" -F "model=intelliai-stt" -F "language=en" \
    "$edge/v1/audio/transcriptions")"
  rm -f "$wav"
  [ "$code" = "200" ] || fail "smoke transcription returned $code, expected 200"
  note "one real transcription through the edge (200)"
else
  warn "INTELLIAI_SMOKE_API_KEY not set — skipped the real-transcription check (create a key with make bootstrap-org)"
fi

echo "SMOKE OK — the stack serves, refuses, and hides exactly what it should"
