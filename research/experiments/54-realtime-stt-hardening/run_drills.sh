#!/usr/bin/env bash
# M54 Phases 21-23 — flood, silence, and short-speech drills against the
# hardened stack (same clips and modes as the M53 battery).
set -u
export PATH="/c/Users/VIKASHAN TECHNOLOGIE/.local/bin:$PATH"
cd "$(dirname "$0")"
URL="ws://127.0.0.1:8000/v1/audio/realtime"
S="C:/Users/VIKASH~1/AppData/Local/Temp/claude/d--Sumit-Projects-IntelliAI-Platform/67762b73-e6aa-43b8-a730-264d0d432d4f/scratchpad"
RUN="uv run --no-sync --with websockets python rt54_client.py"
export PYTHONIOENCODING=utf-8

# Phase 21 — backpressure: 8x flood on both languages.
$RUN "$URL" "$S/m51long/2min.wav" en flood "hardened-en-2min-flood.json" || echo "FAILED en flood"
$RUN "$URL" "$S/m52hclips/real2min.wav" hi flood "hardened-hi-2min-flood.json" || echo "FAILED hi flood"

# Phase 22 — silence (digital silence; VAD must suppress every decode).
$RUN "$URL" "$S/m52clips/silence5.wav" en realtime "hardened-en-silence5.json" || echo "FAILED en silence"
$RUN "$URL" "$S/m52clips/silence5.wav" hi realtime "hardened-hi-silence5.json" || echo "FAILED hi silence"

# Phase 23 — short speech, both languages.
for K in hello yes no okay stop; do
  $RUN "$URL" "$S/m52clips/16k_short_$K.wav" en realtime "hardened-en-short-$K.json" || echo "FAILED en $K"
done
for K in short_haan short_nahin short_theek short_ruko short_haansir; do
  $RUN "$URL" "$S/m52hclips/$K.wav" hi realtime "hardened-hi-$K.json" || echo "FAILED hi $K"
done
echo "DRILLS DONE"
