#!/usr/bin/env bash
# TTS smoke — the stale-image guard made executable (M35).
#
# The M32 trap, never again: an old image under a current compose file
# came up "healthy, and wrong" (reference engine, env silently ignored).
# This smoke fails a stack whose RUNNING code or LOADED artifact is not
# what the source tree ships:
#   §1 identity     — service + version floor (an old image reports old)
#   §2 artifact     — the expected artifact is loaded (not "reference")
#   §3 posture      — M35 keys exist and match the declared posture
#   §4 voices       — the launch voice names are served
#   §5 synthesis    — a real request through the GATEWAY returns WAV
#
# Usage: bash infra/tts-smoke.sh [API_KEY]
#   INTELLIAI_TTS_INFO_URL   (default http://127.0.0.1:8002/info)
#   INTELLIAI_GATEWAY_URL    (default http://127.0.0.1:8000)
#   INTELLIAI_TTS_EXPECTED_ARTIFACT (default kokoro-82m)
#   INTELLIAI_TTS_EXPECTED_OOV      (default espeak)
#   INTELLIAI_SMOKE_API_KEY  (or $1)
set -euo pipefail

INFO_URL="${INTELLIAI_TTS_INFO_URL:-http://127.0.0.1:8002/info}"
GATEWAY_URL="${INTELLIAI_GATEWAY_URL:-http://127.0.0.1:8000}"
EXPECTED_ARTIFACT="${INTELLIAI_TTS_EXPECTED_ARTIFACT:-kokoro-82m}"
EXPECTED_OOV="${INTELLIAI_TTS_EXPECTED_OOV:-espeak}"
VERSION_FLOOR="0.3.0"
API_KEY="${1:-${INTELLIAI_SMOKE_API_KEY:-}}"

fail() { echo "TTS-SMOKE FAIL: $1" >&2; exit 1; }
note() { echo "  ok: $1"; }

INFO_JSON="$(curl -fsS --max-time 10 "$INFO_URL")" || fail "runtime /info unreachable at $INFO_URL"

# python3 on Linux; plain python on Windows dev shells. Windows ships a
# Store ALIAS named python3 that prints an ad and exits nonzero, so a
# candidate only counts if it actually executes.
PYTHON_BIN=""
for candidate in python3 python; do
  if "$candidate" -c "import sys" >/dev/null 2>&1; then PYTHON_BIN="$candidate"; break; fi
done
[ -n "$PYTHON_BIN" ] || fail "no working python available"
json() { printf '%s' "$INFO_JSON" | "$PYTHON_BIN" -c "import json,sys; d=json.load(sys.stdin); print($1)"; }

# §1 identity + version floor — THE stale-image check.
[ "$(json "d['service']")" = "tts-runtime" ] || fail "wrong service identity"
VERSION="$(json "d['service_version']")"
LOWEST="$(printf '%s\n%s\n' "$VERSION" "$VERSION_FLOOR" | sort -V | head -1)"
[ "$LOWEST" = "$VERSION_FLOOR" ] || fail "stale image: runtime reports $VERSION < $VERSION_FLOOR — rebuild before trusting this stack"
note "runtime version $VERSION >= $VERSION_FLOOR"

# §2 the loaded artifact is the declared one, never a silent fallback.
ARTIFACTS="$(json "','.join(m['artifact'] for m in d['models'])")"
case ",$ARTIFACTS," in
  *,"$EXPECTED_ARTIFACT",*) note "artifact $EXPECTED_ARTIFACT loaded" ;;
  *) fail "expected artifact '$EXPECTED_ARTIFACT' not loaded (got: $ARTIFACTS)" ;;
esac

# §3 M35 posture keys exist AND match the declared posture.
NORMALIZATION="$(json "d.get('normalization','MISSING')")"
[ "$NORMALIZATION" = "on" ] || fail "normalization reported '$NORMALIZATION' (expected on)"
OOV="$(json "d.get('oov_fallback','MISSING')")"
[ "$OOV" = "$EXPECTED_OOV" ] || fail "oov_fallback reported '$OOV' (expected $EXPECTED_OOV)"
note "posture: normalization=on oov_fallback=$OOV"

# §4 launch voices served (and legacy aliases still alive).
VOICES="$(json "','.join(d['voices'])")"
for voice in english-female english-male reference-alto; do
  case ",$VOICES," in
    *,"$voice",*) ;;
    *) fail "voice '$voice' not served (got: $VOICES)" ;;
  esac
done
note "voices: $VOICES"

# §5 a real synthesis through the gateway — playable bytes, public shape.
if [ -n "$API_KEY" ]; then
  BODY_FILE="$(mktemp)"; HEADERS_FILE="$(mktemp)"
  trap 'rm -f "$BODY_FILE" "$HEADERS_FILE"' EXIT
  STATUS="$(curl -sS --max-time 120 -o "$BODY_FILE" -D "$HEADERS_FILE" -w '%{http_code}' \
    -X POST "$GATEWAY_URL/v1/audio/speech" \
    -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" \
    -d '{"model":"intelliai-tts","input":"IntelliAI speaks for Sumit at 25% volume, on 12/08/2026.","voice":"english-female"}')"
  [ "$STATUS" = "200" ] || fail "gateway synthesis returned $STATUS"
  head -c 4 "$BODY_FILE" | grep -q RIFF || fail "response is not a WAV (no RIFF magic)"
  SIZE="$(wc -c < "$BODY_FILE")"
  [ "$SIZE" -gt 20000 ] || fail "audio suspiciously small ($SIZE bytes)"
  grep -qi '^x-runtime-envelope' "$HEADERS_FILE" && fail "internal envelope leaked to the public response"
  note "gateway synthesis: 200 audio/wav, $SIZE bytes, no internal headers"
else
  echo "  (no API key given - gateway synthesis check skipped; pass one to run it)"
fi

echo "TTS-SMOKE OK - the stack is running the code and artifact it declares."
