#!/usr/bin/env bash
# M54 Phase 1 — baseline reproduction on the UNCHANGED M53 stack.
# Sequential on purpose: the single hot lane is the design under test.
set -u
cd "$(dirname "$0")"
URL="ws://127.0.0.1:8000/v1/audio/realtime"
S="C:/Users/VIKASH~1/AppData/Local/Temp/claude/d--Sumit-Projects-IntelliAI-Platform/67762b73-e6aa-43b8-a730-264d0d432d4f/scratchpad"
RUN="uv run --with websockets python rt54_client.py"
export PYTHONIOENCODING=utf-8

# English: 5x boss30 (Phase 1 baseline + Phase 7 outlier stats), then long.
for i in 1 2 3 4 5; do
  $RUN "$URL" "$S/m52clips/boss30.wav" en realtime "baseline-en-boss30-r$i.json" || echo "FAILED en boss30 r$i"
done
$RUN "$URL" "$S/m51long/2min.wav"  en realtime "baseline-en-2min.json"  || echo "FAILED en 2min"
$RUN "$URL" "$S/m51long/5min.wav"  en realtime "baseline-en-5min.json"  || echo "FAILED en 5min"
$RUN "$URL" "$S/m51long/10min.wav" en realtime "baseline-en-10min.json" || echo "FAILED en 10min"

# Hindi: 3x real30s (finalization stats), then long.
for i in 1 2 3; do
  $RUN "$URL" "$S/m52hclips/real30s.wav" hi realtime "baseline-hi-real30s-r$i.json" || echo "FAILED hi 30s r$i"
done
$RUN "$URL" "$S/m52hclips/real2min.wav"  hi realtime "baseline-hi-2min.json"  || echo "FAILED hi 2min"
$RUN "$URL" "$S/m52hclips/real5min.wav"  hi realtime "baseline-hi-5min.json"  || echo "FAILED hi 5min"
$RUN "$URL" "$S/m52hclips/real10min.wav" hi realtime "baseline-hi-10min.json" || echo "FAILED hi 10min"
echo "BASELINE BATTERY DONE"
