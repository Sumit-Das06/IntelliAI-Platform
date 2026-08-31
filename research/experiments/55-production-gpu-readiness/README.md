# M55 — Production GPU serving readiness

Evidence for `docs/milestones/55-production-gpu-serving-readiness.md`.
Classification: **PRODUCTION-LIKE-GPU-VERIFIED** (RTX 5070 Laptop —
no designated production GPU box exists yet; see `evidence/hardware.json`).

| tool | purpose |
|---|---|
| `rt55_client.py` / `rt55_concurrent.py` / `gpu_sample.py` | the M54 battery harness, unchanged |
| `run_ladders.sh` | EN 20-run stall battery + HI sessions + c=1/2/4/8 mixed ladder |
| `hi_batch_matrix.py` | Hindi BATCH through the real gateway (GPU external-server mode), n=5, determinism-checked |
| `mixed_workload.py` | EN+HI realtime while batch hammers its own GPU instance |
| `m55_browser_e2e.py` / `m55_mobile.py` | the M53/M54 browser harness |

The batch GPU path uses the M55 engine addition (external-server mode,
`INTELLIAI_STT_QWEN3_SERVER_URL`) with a second pinned llama-server
instance on :8798; the test overlay lives in the session scratchpad —
committed compose files stay CPU-mode. Audio never enters git.
