#!/usr/bin/env bash
# M54 hardened battery — identical clips/order to run_baseline.sh, against
# the restarted (hardened) runtime. Prefix distinguishes the evidence.
set -u
export PATH="/c/Users/VIKASHAN TECHNOLOGIE/.local/bin:$PATH"
cd "$(dirname "$0")"
URL="ws://127.0.0.1:8000/v1/audio/realtime"
S="C:/Users/VIKASH~1/AppData/Local/Temp/claude/d--Sumit-Projects-IntelliAI-Platform/67762b73-e6aa-43b8-a730-264d0d432d4f/scratchpad"
RUN="uv run --no-sync --with websockets python rt54_client.py"
export PYTHONIOENCODING=utf-8
PREFIX="${1:-hardened}"

for i in 1 2 3 4 5; do
  $RUN "$URL" "$S/m52clips/boss30.wav" en realtime "$PREFIX-en-boss30-r$i.json" || echo "FAILED en boss30 r$i"
done
$RUN "$URL" "$S/m51long/2min.wav"  en realtime "$PREFIX-en-2min.json"  || echo "FAILED en 2min"
$RUN "$URL" "$S/m51long/5min.wav"  en realtime "$PREFIX-en-5min.json"  || echo "FAILED en 5min"
$RUN "$URL" "$S/m51long/10min.wav" en realtime "$PREFIX-en-10min.json" || echo "FAILED en 10min"

for i in 1 2 3; do
  $RUN "$URL" "$S/m52hclips/real30s.wav" hi realtime "$PREFIX-hi-real30s-r$i.json" || echo "FAILED hi 30s r$i"
done
$RUN "$URL" "$S/m52hclips/real2min.wav"  hi realtime "$PREFIX-hi-2min.json"  || echo "FAILED hi 2min"
$RUN "$URL" "$S/m52hclips/real5min.wav"  hi realtime "$PREFIX-hi-5min.json"  || echo "FAILED hi 5min"
$RUN "$URL" "$S/m52hclips/real10min.wav" hi realtime "$PREFIX-hi-10min.json" || echo "FAILED hi 10min"
echo "$PREFIX BATTERY DONE"
