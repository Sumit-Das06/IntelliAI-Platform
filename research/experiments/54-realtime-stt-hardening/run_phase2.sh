#!/usr/bin/env bash
# M54 second measurement block: drills, lifecycle, concurrency (+GPU
# sampling), batch regression, quality. Sequential; ~40 min.
set -u
export PATH="/c/Users/VIKASHAN TECHNOLOGIE/.local/bin:$PATH"
cd "$(dirname "$0")"
export PYTHONIOENCODING=utf-8
RUN="uv run --no-sync --with websockets python"

bash run_drills.sh
$RUN rt54_lifecycle.py lifecycle.json || echo "FAILED lifecycle"

# Concurrency ladder with GPU sampling alongside.
uv run --no-sync python gpu_sample.py 90 gpu-c1.json &
$RUN rt54_concurrent.py 1 concurrency-c1 || echo "FAILED c1"
wait
uv run --no-sync python gpu_sample.py 120 gpu-c2.json &
$RUN rt54_concurrent.py 2 concurrency-c2 || echo "FAILED c2"
wait
uv run --no-sync python gpu_sample.py 180 gpu-c4.json &
$RUN rt54_concurrent.py 4 concurrency-c4 || echo "FAILED c4"
wait
# Fairness probe: 4 short sessions + one LOUD 10-minute neighbor.
uv run --no-sync python gpu_sample.py 660 gpu-loud.json &
$RUN rt54_concurrent.py 4 concurrency-c4-loud long || echo "FAILED c4-loud"
wait

uv run --no-sync python batch_regression.py || echo "FAILED batch regression"
uv run --no-sync python m54_quality.py || echo "FAILED quality"
echo "PHASE2 BLOCK DONE"
