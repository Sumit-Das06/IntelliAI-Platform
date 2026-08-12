#!/usr/bin/env bash
# Milestone 17 re-verification after the two fixes: (1) audio beyond the
# measured ceiling refuses loudly instead of silently truncating;
# (2) engine close aborts in-flight spawns so no orphan survives stop.
set -e
REPO="/mnt/d/Sumit Projects/IntelliAI Platform"
VENV="$HOME/venv-intelliai"
EXP="$REPO/research/experiments/17-canary-prep"
export LD_LIBRARY_PATH="$HOME/qwen3-runtime/sysdeps/usr/lib/x86_64-linux-gnu"
export INTELLIAI_STT_SLOTS="qwen3-asr"
export INTELLIAI_STT_QWEN3_SERVER_BINARY="$HOME/qwen3-runtime/llama-b10344/llama-server"
export INTELLIAI_STT_FFMPEG_PATH="$HOME/bin/ffmpeg"
export INTELLIAI_STT_MAX_AUDIO_SECONDS="600"
cd "$REPO"

"$VENV/bin/uvicorn" --factory intelliai_stt_runtime.main:create_app --port 8004 \
  > ~/runtime-linux-reverify.log 2>&1 &
RUNTIME_PID=$!
for i in $(seq 1 60); do
  sleep 5
  if curl -s --max-time 3 http://127.0.0.1:8004/info > /dev/null; then break; fi
done

echo "=== 300s request must now refuse loudly ==="
curl -s -o /tmp/longresp.json -w "%{http_code}\n" -X POST http://127.0.0.1:8004/v1/transcribe \
  -F "file=@$HOME/longaudio/300s.wav;type=audio/wav" \
  -F 'params={"language":"hi"}'
cat /tmp/longresp.json | head -c 400
echo
cp /tmp/longresp.json "$EXP/long-audio-refusal-linux.json"

echo "=== 120s request must still serve ==="
curl -s -o /tmp/ok120.json -w "%{http_code}\n" -X POST http://127.0.0.1:8004/v1/transcribe \
  -F "file=@$HOME/longaudio/120s.wav;type=audio/wav" \
  -F 'params={"language":"hi"}'

echo "=== restart drill (post-fix) ==="
"$VENV/bin/python" research/experiments/17-canary-prep/restart_drill.py \
  --url http://127.0.0.1:8004 \
  --out "$EXP/restart-drill-linux-postfix.json" 2>&1 | tail -12

echo "=== stop runtime immediately after forcing a restart cycle ==="
# Kill the child and stop the runtime WHILE the supervisor is mid-spawn —
# the exact orphan window found in the first session.
for pid in $(pgrep -x llama-server); do kill -9 "$pid"; done
sleep 1.5   # supervisor: backoff(1s) then spawn begins its health wait
kill $RUNTIME_PID 2>/dev/null || true
sleep 8
ORPHANS=$(pgrep -x llama-server | wc -l)
echo "{\"orphans_after_midspawn_stop\": $ORPHANS}" > "$EXP/orphan-accounting-linux-postfix.json"
echo "orphans after mid-spawn stop: $ORPHANS"
echo "REVERIFY COMPLETE"
