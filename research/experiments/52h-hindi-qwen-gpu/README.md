# M52H — Hindi Qwen3-ASR E3 GPU realtime feasibility

Full report: [docs/research/2026-08-28-hindi-qwen-e3-gpu-realtime.md](../../../docs/research/2026-08-28-hindi-qwen-e3-gpu-realtime.md)

## Setup

One focused question: can the UNCHANGED production E3 artifact become
realtime-capable on the laptop's RTX 5070? The GPU runtime is the SAME
llama.cpp commit as the production pin (b10344 / 7a20b417f), CUDA-13.3
variant, so backend is the only variable (`evidence/hardware.json`
records zips, SHAs, flags). Requests mirror the production engine
byte-for-byte; every benchmark decode disables the server prompt cache.

All quality scoring uses REAL Hindi speech: IndicVoices `valid` clips
with pinned-manifest reference texts (`unicode_generic@v2` frozen
ruler). Long sessions are concatenations of UNIQUE real clips
(documented synthetic seams — clip joins, multiple speakers). Audio
stays in the scratchpad; nothing private is committed.

## Files

| file | what |
|---|---|
| `m52h_bench.py` | all benchmark modes (cpu-baseline, gpu-ladder, windows, sim, memory, concurrency, quality) |
| `evidence/cpu-baseline.json` | M52 CPU ladder reproduced through the staging container |
| `evidence/gpu-baseline.json` | same prefixes on GPU (+ prompt-cache effect, recorded separately) |
| `evidence/gpu-window-ladder.json` | 250 ms – 5 s realtime windows |
| `evidence/sim-*.json` | streaming sims (virtual mic clock, real decodes): 30 s growing + 2/5/10 min rolling with VAD-snapped commits, LA2 metrics inline |
| `evidence/quality.json` | 30 real clips: GPU vs CPU vs ground truth (WER/CER), both sides direct llama-server |
| `evidence/long-2min-quality.json` | why single-pass offline is the WRONG long-audio ruler (truncation) — ground truth is the ruler |
| `evidence/short-speech.json` | real short clips (with refs) + TTS shorts (synthetic, labeled) |
| `evidence/hindi-probes.json` | TTS probe sentences (synthetic, qualitative) |
| `evidence/silence.json` | VAD gate + bare-model-on-silence behavior |
| `evidence/gpu-memory.json`, `evidence/concurrency.json` | VRAM/leak profile, c=1/2/4/8 |
| `evidence/service-anomaly.json` | OPEN FINDING: the production runtime SERVICE path produced unstable truncated output on 30 s+ multi-speaker audio while direct child calls stayed stable — isolation matrix inside |
| `m52h_summarize.py` | post-processing: per-clip offline baselines for the long material + the spec-named summary files |
| `evidence/long-offline-per-clip-baseline.json` | each constituent real clip decoded individually on GPU, scored vs truth — isolates streaming penalty (0 / +0.7 / +2.1 pt) from material difficulty |
| `evidence/long-quality-vs-truth.json` | streamed rolling finals vs ground truth (2/5/10 min + the 15 s-window counterfactual) |
| `evidence/fpt.json`, `partial-cadence.json`, `finalization.json`, `stability.json`, `vad.json`, `long-speech.json`, `cpu-vs-gpu.json` | spec-named summaries synthesized from the sims |
| `evidence/sim-real5min-window15.json` | counterfactual: a 15 s window cap does NOT improve long-session p50 (more commit decodes offset smaller windows) |
