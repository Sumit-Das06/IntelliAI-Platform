#!/usr/bin/env bash
# M55 Phases 7-9 — EN + HI c-ladders (c=1/2/4/8) + EN stall battery
# (20 boss30 sessions) + HI long sessions, with GPU sampling.
set -u
export PATH="/c/Users/VIKASHAN TECHNOLOGIE/.local/bin:$PATH"
cd "$(dirname "$0")"
URL="ws://127.0.0.1:8000/v1/audio/realtime"
S="C:/Users/VIKASH~1/AppData/Local/Temp/claude/d--Sumit-Projects-IntelliAI-Platform/67762b73-e6aa-43b8-a730-264d0d432d4f/scratchpad"
RUN="uv run --no-sync --with websockets python rt55_client.py"
CON="uv run --no-sync --with websockets python rt55_concurrent.py"
export PYTHONIOENCODING=utf-8

# EN stall battery: 20 repeated boss30 sessions (Phase 8).
for i in $(seq 1 20); do
  $RUN "$URL" "$S/m52clips/boss30.wav" en realtime "stall-en-boss30-r$i.json" || echo "FAILED stall r$i"
done

# HI ladder base runs + longs (Phase 9-10).
for i in 1 2 3; do
  $RUN "$URL" "$S/m52hclips/real30s.wav" hi realtime "prod-hi-real30s-r$i.json" || echo "FAILED hi r$i"
done
$RUN "$URL" "$S/m52hclips/real2min.wav"  hi realtime "prod-hi-2min.json"  || echo "FAILED hi 2min"
$RUN "$URL" "$S/m52hclips/real5min.wav"  hi realtime "prod-hi-5min.json"  || echo "FAILED hi 5min"
$RUN "$URL" "$S/m52hclips/real10min.wav" hi realtime "prod-hi-10min.json" || echo "FAILED hi 10min"

# Concurrency ladder, mixed EN+HI (Phases 7/9/15), GPU sampled.
uv run --no-sync python gpu_sample.py 90 gpu-c1.json &
$CON 1 prod-c1 || echo "FAILED c1"
wait
uv run --no-sync python gpu_sample.py 120 gpu-c2.json &
$CON 2 prod-c2 || echo "FAILED c2"
wait
uv run --no-sync python gpu_sample.py 180 gpu-c4.json &
$CON 4 prod-c4 || echo "FAILED c4"
wait
uv run --no-sync python gpu_sample.py 240 gpu-c8.json &
$CON 8 prod-c8 || echo "FAILED c8"
wait
echo "LADDERS DONE"
