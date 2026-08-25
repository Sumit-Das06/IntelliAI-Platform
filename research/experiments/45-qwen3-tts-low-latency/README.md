# M45 — Qwen3-TTS 0.6B Low-Latency / Streaming Optimization (research)

Research-only instruments and evidence for the M45 runtime/streaming
track. No fine-tuning, no weight changes, no production changes;
Kokoro remains production. Report:
`docs/research/2026-08-25-qwen3-tts-low-latency.md`.

## Identity (frozen, = M44)

`Qwen/Qwen3-TTS-12Hz-0.6B-Base` @ `5d839924…` (model.safetensors
sha256 `180b3b10…`), tokenizer 12Hz @ `7dd38ad4…`, `qwen-tts` 0.1.1,
clone/ICL mode with the pinned LJ001-0004 reference. GPU: RTX 5070
Laptop 8 GB (sm_120), WSL2, torch 2.11.0+cu128.

## Instruments (run in the WSL research venv; EXPERIMENTAL = runtime-level only)

- `harness/m45_profile.py` — component profile via GPU-synced timing
  wrappers (trunk / sub-talker / codec decode / prompt build), cold vs
  warm, cached-prompt comparison, M34 length ladder.
- `harness/m45_fastsub.py` — EXPERIMENTAL manual 15-step sub-talker
  sampling loop replacing the per-frame HF generate() call (same
  math/warpers; proven output-identical under the seed protocol).
- `harness/m45_fastsub2_failed.py` — the StaticCache +
  torch.compile(reduce-overhead) attempt, kept as the record of the
  CUDA-graph failure mode (2 attempts, same overwrite error).
- `harness/m45_stream.py` — EXPERIMENTAL true frame-level streaming:
  forward hook collects each frame's codes; growing-prefix decode
  through the causal Code2Wav with a right-edge guard; continuity
  gold-compared against one-shot decode of the same codes.
- `harness/m45_sentchunk.py` — sentence-chunked fallback (measured,
  rejected as dominated).
- `harness/m45_conc.py` — c=1/2/4/8 ladder + 50-request leak check.
- `harness/m45_vllm_bench.py` — vLLM-Omni 0.26.0 wire-level streaming
  bench (`POST /v1/audio/speech`, stream=true, PCM).

## Headline results

- Bottleneck located: sub-talker per-frame HF generate() ≈ 73% of
  wall; codec decode ~free; per-frame ~120 ms vs the 83 ms real-time
  budget (kernel-launch-bound).
- TRUE streaming achieved on the official runtime: **TTFA 0.80–0.82 s**
  text-length-independent, continuity exact (Δlen 0, RMS ≤ 0.0008).
- No runtime reached RTF < 1: official 1.54–1.65, fastsub 1.39–1.45,
  vLLM-Omni 1.36–3.86 (steady TTFA ~6.5 s on this GPU).
- Concurrency collapses (capacity 1 stream); no VRAM/RAM leaks.
- **Decision C — Qwen still too slow on this hardware; deferred.**
  Re-entry trigger: a GPU with per-frame ≲ 60 ms (rented-GPU rerun of
  these unchanged harnesses), or vLLM-Omni maturing on sm_120.

WAVs live outside git (session scratchpad `m45-audio/`, WSL
`~/m45/audio/`). The vLLM venv is `~/m45/venv-vllm` (WSL, ~11 GB) —
disposable.
