#!/usr/bin/env bash
# Milestone 17 Linux validation session (WSL2 Ubuntu; honestly labeled,
# NOT VPS hardware). Prereqs (user-space, no sudo): pinned b10344
# ubuntu-x64 build + libgomp extract under ~/qwen3-runtime, static
# ffmpeg/ffprobe in ~/bin, workspace venv at ~/venv-intelliai.
set -e
REPO="/mnt/d/Sumit Projects/IntelliAI Platform"
VENV="$HOME/venv-intelliai"
EXP="$REPO/research/experiments/17-canary-prep"
export LD_LIBRARY_PATH="$HOME/qwen3-runtime/sysdeps/usr/lib/x86_64-linux-gnu"
export INTELLIAI_STT_SLOTS="qwen3-asr"
export INTELLIAI_STT_QWEN3_SERVER_BINARY="$HOME/qwen3-runtime/llama-b10344/llama-server"
export INTELLIAI_STT_FFMPEG_PATH="$HOME/bin/ffmpeg"
cd "$REPO"

echo "=== [$(date -Is)] building long-audio probes ==="
mkdir -p ~/longaudio
ls ml/datasets/data/indicvoices/hindi/valid/*.flac | head -120 > ~/longaudio/all.txt
for S in 60 120 300 600; do
  if [ ! -f ~/longaudio/${S}s.wav ]; then
    : > ~/longaudio/list.txt
    TOTAL=0
    while read -r f; do
      D=$("$HOME/bin/ffprobe" -v error -show_entries format=duration -of csv=p=0 "$f")
      TOTAL=$(awk -v a="$TOTAL" -v b="$D" 'BEGIN {print a + b}')
      printf "file '%s/%s'\n" "$REPO" "$f" >> ~/longaudio/list.txt
      ENOUGH=$(awk -v t="$TOTAL" -v s="$S" 'BEGIN {print (t >= s) ? 1 : 0}')
      [ "$ENOUGH" = "1" ] && break
    done < ~/longaudio/all.txt
    "$HOME/bin/ffmpeg" -y -loglevel error -f concat -safe 0 -i ~/longaudio/list.txt \
      -t "$S" -ar 16000 -ac 1 -sample_fmt s16 ~/longaudio/${S}s.wav
  fi
done
ls -la ~/longaudio/*.wav

echo "=== [$(date -Is)] booting runtime (linux, qwen3-asr) ==="
"$VENV/bin/uvicorn" --factory intelliai_stt_runtime.main:create_app --port 8004 \
  > ~/runtime-linux.log 2>&1 &
RUNTIME_PID=$!
for i in $(seq 1 60); do
  sleep 5
  if curl -s --max-time 3 http://127.0.0.1:8004/info > /dev/null; then break; fi
done
curl -s http://127.0.0.1:8004/info > "$EXP/info-linux.json" || true
curl -s http://127.0.0.1:8004/health/ready
echo

echo "=== [$(date -Is)] full frozen hi eval on linux ==="
"$VENV/bin/python" -m intelliai_evaluation run \
  --dataset ml/evaluation/stt/datasets/stt-hi-public-eval-v1.json \
  --data-dir ml/datasets/data \
  --url http://127.0.0.1:8004 \
  --manifest ml/evaluation/manifests/research.json \
  --model research:qwen3-asr-0.6b \
  --language hi \
  --engine llama.cpp \
  --notes "Milestone 17: LINUX validation of the pinned b10344 ubuntu-x64 runtime (GNU 11.4.0; llama-server sha 9b7b699e) on WSL2 Ubuntu 24.04 - same physical machine as all prior records, Linux kernel/userland, NOT a VPS. Same frozen manifest cf643146, ruler, harness, greedy decode." \
  --out ml/evaluation/stt/results/2026-08-12-research-qwen3-asr-0.6b-hi-17-linux.json 2>&1 | tail -6

echo "=== [$(date -Is)] concurrency ladder on linux ==="
(
  while true; do
    CPU=$(top -bn1 | grep "Cpu(s)" | awk '{print 100 - $8}')
    RSS=$(pgrep -x llama-server | xargs -I{} cat /proc/{}/status 2>/dev/null | grep VmRSS | awk '{s+=$2} END {print s}')
    echo "{\"cpu_pct\": ${CPU:-0}, \"llama_rss_kib\": ${RSS:-0}}"
    sleep 1
  done > "$EXP/sidecar-linux.jsonl"
) &
SIDECAR_PID=$!
"$VENV/bin/python" -m intelliai_evaluation bench \
  --clip weights/bench-hi-median.wav \
  --runtime-url http://127.0.0.1:8004 \
  --artifact qwen3-asr-0.6b \
  --language hi \
  --levels 1,5,10,20 \
  --repetitions 5 \
  --hardware "WSL2 Ubuntu 24.04 on Intel64 F6M183 (24 threads) - Linux validation on the dev laptop, NOT VPS hardware" \
  --notes "Milestone 17 Linux ladder: pinned b10344 ubuntu-x64 llama-server, same clip and methodology as the Milestone 16 Windows ladder." \
  --out ml/evaluation/stt/benchmarks/2026-08-12-qwen3-asr-0.6b-linux-wsl2-ladder.json 2>&1 | tail -4
kill $SIDECAR_PID 2>/dev/null || true

echo "=== [$(date -Is)] long-audio probe ==="
"$VENV/bin/python" research/experiments/17-canary-prep/long_audio_probe.py \
  --url http://127.0.0.1:8004 \
  --clips-dir ~/longaudio \
  --short-clip weights/bench-hi-median.wav \
  --out "$EXP/long-audio-linux.json" 2>&1 | tail -40

echo "=== [$(date -Is)] supervised restart drill (live) ==="
"$VENV/bin/python" research/experiments/17-canary-prep/restart_drill.py \
  --url http://127.0.0.1:8004 \
  --out "$EXP/restart-drill-linux.json" 2>&1 | tail -40

echo "=== [$(date -Is)] failure drills (kill phase) ==="
"$VENV/bin/python" research/experiments/16-qwen3-switching/failure_drills.py \
  --url http://127.0.0.1:8004 --phase kill --out "$EXP/failure-drills-linux.json" > /dev/null || true

kill $RUNTIME_PID 2>/dev/null || true
sleep 5
ORPHANS=$(pgrep -x llama-server | wc -l)
echo "{\"orphans_after_stop\": $ORPHANS}" > "$EXP/orphan-accounting-linux.json"
echo "orphans after stop: $ORPHANS"
echo "SESSION LINUX COMPLETE"
