#!/bin/bash
# M53 staging battery — every session through the REAL gateway WS.
set -u
REPO="/d/Sumit Projects/IntelliAI Platform"
RT="$REPO/research/experiments/53-realtime-stt/rt_client.py"
SC="C:\\Users\\VIKASH~1\\AppData\\Local\\Temp\\claude\\d--Sumit-Projects-IntelliAI-Platform\\67762b73-e6aa-43b8-a730-264d0d432d4f\\scratchpad"
URL="ws://127.0.0.1:8000/v1/audio/realtime"
cd "$REPO"
export PYTHONIOENCODING=utf-8

run() { python "$RT" "$URL" "$1" "$2" "$3" "$4" 2>&1 | tail -1; }

# ── English ──────────────────────────────────────────────────────────
run "$SC\\m52clips\\boss30.wav" en realtime en-boss30-realtime.json
run "$SC\\m51long\\2min.wav" en realtime en-2min-realtime.json
run "$SC\\m51long\\5min.wav" en realtime en-5min-realtime.json
run "$SC\\m51long\\10min.wav" en realtime en-10min-realtime.json
for K in hello yes no okay stop; do
  run "$SC\\m52clips\\16k_short_$K.wav" en realtime "en-short-$K.json"
done
run "$SC\\m52clips\\silence5.wav" en realtime en-silence5.json
run "$SC\\m51long\\2min.wav" en flood en-2min-flood.json

# ── Hindi ────────────────────────────────────────────────────────────
run "$SC\\m52hclips\\real30s.wav" hi realtime hi-real30s-realtime.json
run "$SC\\m52hclips\\real2min.wav" hi realtime hi-real2min-realtime.json
run "$SC\\m52hclips\\real5min.wav" hi realtime hi-real5min-realtime.json
run "$SC\\m52hclips\\real10min.wav" hi realtime hi-real10min-realtime.json
for K in short_haan short_nahin short_theek short_chalo short_haansir; do
  run "$SC\\m52hclips\\$K.wav" hi realtime "hi-$K.json"
done
for i in 0 1 2; do
  run "$SC\\m52hclips\\realshort_$i.wav" hi realtime "hi-realshort_$i.json"
done
run "$SC\\m52clips\\silence5.wav" hi realtime hi-silence5.json

echo BATTERY-DONE
