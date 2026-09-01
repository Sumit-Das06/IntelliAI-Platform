# M57 — Smart Correction Runtime (staging only)

Evidence for `docs/milestones/57-smart-correction-runtime.md`.

Live runs go through the REAL authenticated gateway
(`POST /v1/text/corrections`) on the local production-shaped stack;
the correction model serves from its own pinned llama-server (:8802,
`tools/correction/launch_correction_gpu.py`). `live_battery.py` runs
the spec's Phase 19-23 cases + full-stack latency;
`realtime_regression.py` measures realtime under a worst-case
correction hammer; `browser_e2e.py` drives the ✨ Improve flow
(toggle, share, stale-edit drill) with a fake microphone. No audio or
private recordings; transcripts in evidence are the authored test
sentences.
