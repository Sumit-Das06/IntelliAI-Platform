# Qwen3-TTS 0.6B Low-Latency / Streaming Optimization (Milestone 45)

| | |
|---|---|
| **Status** | COMPLETE — MEASURED. TRUE streaming built and proven on the official runtime (TTFA 0.80 s, exact continuity), but no runtime reached RTF < 1 on the 8 GB laptop GPU (best 1.39; vLLM-Omni 1.36–3.86 with 6.5 s TTFA). Decision C — Qwen still too slow on this hardware; Kokoro keeps production. |
| **Date** | 2026-08-25 |
| **Question** | Can Qwen3-TTS 0.6B Base become responsive enough (TTFA ≤ ~1 s on the local GPU) through inference/runtime/streaming work alone — no fine-tuning, no weight changes? |
| **Scope** | Research only. Kokoro stays production; no production/API/catalog changes; English only; the M44 model identity frozen. |
| **Evidence** | `research/experiments/45-qwen3-tts-low-latency/` (profiles, benches, streaming proofs) · WAVs outside git |
| **Labels** | MEASURED · REPO-VERIFIED · WEB-RESEARCHED · EXPERIMENTAL · ESTIMATED · UNKNOWN |

## 1. Frozen identity (Phase 1) — REPO-VERIFIED

Same pins as M44, byte-verified at run start: `Qwen/Qwen3-TTS-12Hz-0.6B-Base`
@ `5d83992436eae1d760afd27aff78a71d676296fc`, local dir
`model.safetensors` sha256 `180b3b10…`; tokenizer 12Hz @ `7dd38ad4…`;
`qwen-tts` 0.1.1; clone/ICL mode with the pinned LJ001-0004 reference
(hash-pinned in the M44 manifest). No fine-tuned checkpoint, no weight
edits anywhere in this milestone.

## 2. Hardware (Phase 3) — MEASURED

RTX 5070 Laptop 8151 MiB (driver 591.91) · Intel i7-14650HX · WSL2
Ubuntu, 15 GiB RAM · Python 3.12.3 · torch 2.11.0+cu128 (CUDA verified)
· transformers 4.57.3.

## 3. M44 baseline reproduced (Phase 2) — MEASURED

**Reproduced = YES.** Same pinned model/ref through the same wrapper:
RTF 1.54–1.65 across the 22→2039-char ladder (M44 band 1.42–1.60;
trap-set conditions reproduce inside noise), zero failures, VRAM peak
2.3–2.9 GiB alloc. TTFA = total wall (no streaming in `qwen-tts`
0.1.1, re-confirmed at source): 2.1 s (22 chars) → 6.2 s (64) →
46.5 s (501) → 177.8 s (2039). Full rows:
`evidence/profile-bf16.json`.

## 4. The latency profile (Phase 4) — MEASURED

Instrumented with GPU-synced timing wrappers around the runtime's own
methods (weights untouched). Where the time actually goes, 2039-char
row (177.8 s total):

| Component | Time | Share | Meaning |
|---|---|---|---|
| **Sub-talker (code_predictor)** | **129.5 s** | **~73%** | The official loop makes a FULL HF `generate()` call per audio frame (12 frames/s of audio), each sampling 15 codebook tokens sequentially |
| Talker trunk (28-layer AR) | 42.8 s | ~24% | ~30 ms/frame |
| Codec decode (Code2Wav) | 0.84 s | ~0.5% | effectively FREE — 115 s of audio decoded in under a second |
| Prompt/tokenize/other | ~4.6 s | ~2.6% | |

Per frame ≈ 120 ms against an 83 ms real-time budget (12 Hz). The
model is **kernel-launch-bound, not compute-bound**, on this laptop
GPU: each frame runs ~16 tiny sequential forwards. The talker loop is
the latency; decoding is not. This kills the naive "stream the codec"
theory as a full fix — streaming solves TTFA but cannot raise the
production rate.

## 5. Cold vs warm (Phase 5) — MEASURED

Model load 5.9 s (one-time). Cold first request 6.40 s vs warm 5.91–
6.30 s on the same text — **cold initialization is NOT the cause**;
the AR loop dominates identically warm or cold. A resident warm model
is assumed for every number in this report.

## 6. Reference conditioning / prompt caching (Phase 6) — MEASURED

The runtime officially supports prompt reuse:
`create_voice_clone_prompt()` returns the ref-audio codec codes (65
frames) + speaker embedding, and `generate_voice_clone(...,
voice_clone_prompt=items)` accepts them — no API abuse needed.
Measured: first build 1.50 s (codec encode 1.00 s + speaker embed
0.22 s, cold); per-call rebuild thereafter ~0.15–0.2 s. Caching saves
that ~0.2 s/request — real but minor; adopted for every M45
experiment. One wrinkle recorded: ICL decode prepends the ref codes on
EVERY request (then cuts them), so each request also decodes 5.1 s of
reference audio — measurable but small, since decode is ~free.

## 7. Precision (Phase 7) — MEASURED

bf16 is the shipped/default precision and every number here is bf16.
fp16/fp32 sweeps were deliberately NOT run once the profile showed the
loop is kernel-launch-bound: precision changes bandwidth/compute per
kernel, not the number of launches, so it cannot close a 45% RTF gap —
and fp32 would only be slower. Recorded as a scoping decision, not an
omission.

## 8. GPU/runtime optimization (Phase 8) — MEASURED, one variable at a time

One variable at a time, all EXPERIMENTAL (runtime-level only, weights
untouched):

1. **fastsub** — replace the per-frame HF `generate()` into the
   sub-talker with a manual 15-step loop (same forward math, same
   warper chain: temperature 0.9 + top-k 50, multinomial). RTF
   1.54–1.65 → **1.39–1.45** (~10%). Verdict: real but small — the 16
   sequential tiny forwards themselves are the cost, not HF's
   bookkeeping.
2. **fastsub + torch.compile(reduce-overhead)** on talker.model +
   code_predictor.model — **FAILED**: `accessing tensor output of
   CUDAGraphs that has been overwritten` (transformers output
   dataclasses hold graph buffers across replays).
3. **fastsub v2: StaticCache + compiled step fn +
   `cudagraph_mark_step_begin()` + cloned outputs — FAILED with the
   same CUDA-graph overwrite error inside the compiled region** (guard
   evaluation touches graph-owned cache tensors). A hand-written
   `torch.cuda.CUDAGraph` capture per sub-step remains the theoretical
   fix (~25 ms/frame sub-talker → RTF ~0.75 ESTIMATED) but is exactly
   the engineering a serving runtime should own, not a research
   harness — recorded as the one identified path to RTF < 1 on this
   GPU, unproven.
4. Pinned memory / transfer trimming: not applicable — profile shows
   no measurable H2D/D2H component; decode already GPU-resident.

## 9. Inference servers (Phase 9) — MEASURED (vLLM-Omni) + WEB-RESEARCHED

**vLLM-Omni 0.26.0** (vllm 0.26.0, torch 2.11, fresh venv, prebuilt
wheels; Python 3.12; WSL2 counts as Linux) serving the SAME pinned
model dir. Bring-up cost on this box, recorded honestly: (a)
flashinfer JIT needs nvcc — fixed by pointing CUDA_HOME at the
pip-bundled `nvidia/cu13` toolkit; (b) flashinfer sampler JIT then
hits a header/compiler mismatch on sm_120 — worked around with
`VLLM_USE_FLASHINFER_SAMPLER=0` (torch-native sampling); (c)
`--allowed-local-media-path` required for file:// reference audio.
Server boots in 80–230 s.

Measured through `POST /v1/audio/speech` (stream=true, PCM on the
wire — their Code2Wav window = 25 frames ≈ 2.08 s audio/chunk):

| Text | TTFA | Total | Audio | RTF |
|---|---|---|---|---|
| 22 chars | 6.13 s | 6.2 s | 1.6 s | 3.86 |
| 64 chars (first-ever request) | 47.9 s | 61.5 s | 6.0 s | 10.3 (warm-up/JIT) |
| 120 chars | 6.55 s | 26.0 s | 12.0 s | 2.17 |
| 501 chars | 6.52 s | 52.6 s | 36.9 s | 1.42 |
| 795 chars | 6.60 s | 193.3 s | 64.4 s | 3.00 |
| 1027 chars | 6.86 s | 123.9 s | 78.6 s | 1.58 |
| 2039 chars | 5.96 s | 200.8 s | 147.2 s | 1.36 |

**Verdict: on THIS GPU, vLLM-Omni is not faster than the official
runtime** — steady TTFA ~6.5 s (their first 25-frame window alone
breaches the 1 s gate) and RTF 1.36–3.86 with high variance. True
streaming works mechanically, but chunks arrive slower than playback.
The "97 ms E2E" card claim is a datacenter-GPU number; it did not
transfer to an 8 GB sm_120 laptop through the released 0.26 stack.
Evidence: `evidence/vllm-stream.json`, `vllm-serve.log` excerpts.

## 10. Streaming investigation (Phases 10-11) — MEASURED, EXPERIMENTAL

True-streaming definition used throughout: PCM chunks must exist
materially BEFORE total synthesis completes; whole-file-then-chunked
HTTP is NOT streaming.

- **Official runtime: NO streaming exists.** Re-verified at source:
  `generate_voice_clone` runs the full talker generate, then ONE codec
  decode at the end; the `non_streaming_mode` flag only changes how
  TEXT is interleaved into the prompt ("simulates streaming text
  input… rather than enabling true streaming"). Documented limitation.
- **EXPERIMENTAL hook streamer (ours)** — no upstream edits, no weight
  changes: a forward hook on the talker collects each frame's
  16-codebook code the moment the official loop samples it (the loop
  already returns it per step); a consumer decodes the growing prefix
  through the CAUSAL Code2Wav decoder (verified causal: CausalConvNet
  / CausalTransConvNet / sliding-window attention) and emits only new
  samples, holding back a 2-frame right-edge guard until final flush.
  Decode is ~free (§4), so re-decoding the prefix costs nothing
  material.

Measured (fastsub on, first chunk 6 frames = 0.5 s audio, then
24-frame chunks):

| Text | TTFA | Total | Chunks | Continuity vs one-shot decode of the SAME codes |
|---|---|---|---|---|
| 22 chars | **0.803 s** | 2.06 s | 2 | len Δ 0 · max abs 0.011 · RMS 0.00026 |
| 64 chars | 1.286 s | 6.75 s | 3 | len Δ 0 · max abs 0.023 · RMS 0.00083 |
| 501 chars | **0.815 s** | 43.4 s | 17 | len Δ 0 · max abs 0.030 · RMS 0.00080 |

**TRUE streaming by the strict definition** — first PCM at 0.8 s while
synthesis continues for up to 43 s. TTFA is now text-length-
independent. THE catch (§18): chunks carry 1.92 s of audio but arrive
every ~2.6–2.8 s, so playback starves after the first chunk — at RTF
~1.4 streaming fixes the START, not the FLOW. Cancellation: the
producer thread runs the official generate; dropping the consumer +
`h.remove()` abandons cleanly (no orphan CUDA work observed).
Evidence: `evidence/stream-fastsub-v2.json` (plus the superseded
first-cut run kept as `stream-fastsub.json`, whose naive fixed-hop
accounting mis-cut chunk boundaries — RMS 0.10 — documented as the
failure that motivated prefix-decode).

## 11. Sentence-level chunking fallback (Phase 12) — MEASURED

Labeled honestly: sentence-chunked progressive playback, NOT
model-native streaming. Measured (fastsub on, cached prompt):

| Text | Sentences | TTFA (= sentence-1 wall) | Total | RTF |
|---|---|---|---|---|
| 120 chars | 2 | 7.49 s | 17.4 s | 1.96 |
| 501 chars | 4 | 8.48 s | 51.9 s | 1.68 |

**Strictly dominated by the frame-level hook streamer** (TTFA 0.8 s):
you wait for the entire first sentence before any audio, per-sentence
calls re-pay prompt/prefill overhead (RTF worsens 1.4 → 1.7-2.0), and
seams reset prosody. Not carried into the matrix as a candidate;
recorded so nobody re-proposes it. Evidence: `evidence/sentchunk.json`.

## 12. Continuity proofs (Phase 13) — MEASURED

Gold = ONE decode of the identical ref+code sequence with the same
exact ref cut. Streamed concatenation: **length delta 0 samples on
every text; max abs diff ≤ 0.030; RMS ≤ 0.00083** (bf16
nondeterminism across decode invocations — inaudible). No seam
silence, no duplication, no missing audio, no timing discontinuity —
the M36/M37 evidence standard, met by construction (each emission is
literally the next slice of the causal decoder's stable prefix).

## 13. Quality regression (Phases 14-15) — MEASURED, frozen M44 sets

The retained optimization (fastsub) and the hook streamer both leave
the CODES untouched — the streamer decodes the identical codes (§12),
and fastsub proved SAMPLING-EQUIVALENT the strong way: an unmodified-
runtime repeat under the same seed protocol produced **identical
aggregates to four decimals** on both sets (trap 0.0703/0.0245, OOV
0.2358/0.1482 — same numbers for `--opt none` and `--opt fastsub`,
i.e., same draws → same audio → same judge result). Zero regression,
by construction and by measurement.

Frozen-set results (gateway whisper judge, M44 discipline), with the
honest run-to-run context this exercise surfaced:

| Set | M44 Base run | M45 runs (both paths) | Kokoro |
|---|---|---|---|
| LJ held-out (100) | 0.0478 | **0.0468** | 0.0535 |
| M33 trap (25) | 0.0515 | 0.0703 | 0.0659 |
| M44 OOV (12) | 0.1724 | 0.2358 | 0.1085 |

LJ-100 (the only large set) reproduces tightly (±0.001). The trap/OOV
deltas vs M44 quantify **seed-to-seed sampling variance of the model
itself on small sets** (N=25/12, do_sample=true): trap band
[0.0515, 0.0703], OOV band [0.1724, 0.2358]. Two standing facts
survive any draw: clean-text quality stays at-or-better-than Kokoro's
level on the big set, and the OOV/brand class stays measurably WORSE
than Kokoro in every rep. Proper names (Sumit/Priya/Rajesh) remain
clean across reps; brand/tech terms remain the slip class. Evidence:
`evidence/fastsub-{trap,oov,lj}-roundtrip.json`,
`evidence/base-{trap,oov}-rep2-roundtrip.json`.

## 14. Concurrency (Phase 16) — MEASURED, local hardware measurement (not production capacity)

Official runtime, one process, thread pool (the shape our gateway
would use), 66-char text, 2×c requests per rung:

| c | ok/req | p50 | p95 | throughput | VRAM peak |
|---|---|---|---|---|---|
| 1 | 2/2 | 5.9 s | 5.5 s | 0.175 rps | 2.40 GiB |
| 2 | 4/4 | 17.6 s | 17.6 s | 0.114 rps | 2.44 GiB |
| 4 | 8/8 | 72.7 s | 76.5 s | 0.055 rps | 2.51 GiB |
| 8 | 16/16 | 250.1 s | 267.6 s | 0.032 rps | 2.61 GiB |

Zero failures, but **throughput FALLS as concurrency rises** (GIL +
kernel-launch thrash between interleaved tiny kernels). Practical
capacity of this runtime on this GPU: **one concurrent stream** — and
that one stream is already slower than real time. vLLM would be the
concurrency answer in principle; on this GPU it lost the
single-stream race first (§9).

## 15. Memory (Phase 17) — MEASURED

Load: 2.19 GiB VRAM alloc / 2.63 GiB reserved; warm steady-state
identical. 50 back-to-back requests: VRAM alloc flat at 2186.8 MiB
(byte-identical), reserved flat at 2806 MiB after request 10, RSS
2437 → 2446 MiB (+9 MiB over 50 requests — allocator noise, not
growth). **No VRAM leak, no RAM leak, no orphan processes** (checked
via pgrep after runs). Fits the 8 GB GPU with ~5 GiB headroom.

## 16. Quantization (Phase 19)

NOT attempted, with the reason on record (the spec's own order: only
after runtime/streaming measurement, and only if needed): the profile
(§4) shows the loop is **kernel-launch-bound, not
bandwidth/compute-bound** — INT8/4-bit shrinks the work per kernel
but launches the same ~16 sequential kernels per frame, so it cannot
close the RTF gap; VRAM is not a constraint (2.4 of 8 GiB); and
lower-bit inference risks exactly the quality axis the gates protect.
Lower-bit ≠ faster here.

## 17. Optimization matrix (Phase 20)

| Candidate | Runtime | Precision | Streaming | TTFA | TTFB | RTF | VRAM | RAM | Quality | Verdict |
|-----------|---------|-----------|-----------|------|------|-----|------|-----|---------|---------|
| Qwen official baseline | qwen-tts 0.1.1 | bf16 | none | = total (2.1–178 s) | = TTFA | 1.54–1.65 | 2.9 GiB | 2.7 GiB | M44 baseline | too slow, no stream |
| Qwen warm + cached prompt | qwen-tts 0.1.1 | bf16 | none | −0.2 s vs above | — | unchanged | same | same | unchanged | minor win, adopted |
| Qwen fastsub (EXPERIMENTAL) | manual sub-talker loop | bf16 | none | = total | — | **1.39–1.45** | 2.4–2.9 GiB | same | **identical (proven)** | ~10%, kept |
| Qwen fastsub+compile v1/v2 | torch.compile reduce-overhead | bf16 | — | — | — | — | — | — | — | **FAILED ×2** (CUDA-graph overwrite) |
| Qwen hook streamer (EXPERIMENTAL) | qwen-tts + forward hook + prefix decode | bf16 | **TRUE (frame-level)** | **0.80–0.82 s** | first chunk | 1.39–1.45 | same | same | identical codes; continuity exact | TTFA gate MET; playback starves at RTF>1 |
| Qwen sentence-chunked | per-sentence calls | bf16 | pseudo | 7.5–8.5 s | — | 1.68–1.96 | same | same | seams reset prosody | dominated, rejected |
| Qwen via vLLM-Omni 0.26 | vllm serve --omni | bf16 | TRUE (25-frame chunks) | ~6.5 s steady (47.9 s first) | 6.5 s | 1.36–3.86 | server-managed | — | not judged (slower on arrival) | loses to official runtime HERE |
| Qwen quantized | — | int8/4bit | — | — | — | — | — | — | — | not attempted (§16 rationale) |
| **Kokoro hardened (reference)** | production gateway | fp32 CPU | TRUE (M36) | **0.4–1.6 s** | same | **0.17–0.28** | — | ~2.4 GiB | 0.0535 LJ / 0.0659 trap / 0.1085 OOV | **wins** |

## 18. UX comparison vs Kokoro (Phase 18)

"Would a real user perceive Qwen as responsive?" — split honestly in
two:

- **Start**: YES, fixed. The experimental streamer starts audio in
  0.8 s regardless of text length — indistinguishable from Kokoro's
  0.4–1.6 s streamed start.
- **Flow**: NO, and nothing measured here fixes it. Every runtime on
  this GPU produces audio slower than it plays (best RTF 1.39): after
  the first 0.5 s chunk, the next 1.9 s of audio needs ~2.7 s of wall,
  so playback stalls ~0.7 s per chunk, forever. Buffering the deficit
  away turns TTFA back into ~0.4×(audio length) — the wall streaming
  was supposed to remove. A 20 s answer either stutters throughout or
  starts ~8 s late; Kokoro does neither.

Kokoro serves the same request with TTFA 0.4–1.6 s, RTF 0.18 on CPU,
c=8 clean, and better OOV. On this hardware there is no configuration
in which a user prefers the Qwen experience.

## 19. Success gates (Phase 21)

| Gate | Target | Result |
|---|---|---|
| Primary: TTFA | ≤ 1.0 s | **MET** (0.80–0.82 s, experimental streamer) — but see RTF |
| Preferred: RTF | < 1 | **FAILED on every runtime**: 1.39 best (fastsub), 1.36–3.86 (vLLM), 1.54 (official) |
| Quality | no material regression | **MET** — retained optimizations proven output-identical; model's own small-set variance documented |
| Safety | no corruption/runaway/dup/missing | **MET** — continuity exact (Δlen 0), zero failures in 137+180 generations |
| Resource | fits 8 GB | **MET** — 2.4–2.9 GiB alloc, no leaks over 50 requests |
| Concurrency | practical for serving | **FAILED** — throughput falls as c rises; capacity = 1 stream, itself sub-real-time |
| Streaming | real progressive audio | **MET (EXPERIMENTAL)** — true frame-level streaming with exact continuity |

The composite fails on the axis no runtime trick reached: production
rate. TTFA was never the disease — RTF > 1 is.

## 20. Decision (Phase 23)

**C. QWEN 0.6B STILL TOO SLOW** — on the available GPU.

Not D: true streaming IS practically achievable (built, measured,
continuity-proven — that result is real and reusable). Not E: quality
survived untouched. The blocker is singular and now precisely located:
**the talker loop produces 12 Hz frames at ~105–120 ms each on this
kernel-launch-bound laptop GPU, and every runtime measured — official,
manual fast loop, torch.compile (failed), vLLM-Omni — stays above
real time.** Streaming fixed the start of the utterance; nothing fixed
the middle.

What would flip this to a re-run, in order of credibility: (1) a GPU
whose per-frame wall is ≲ 60 ms — a desktop/datacenter class card;
one rented-GPU afternoon would answer it (the same harnesses run
unchanged); (2) vLLM-Omni maturing on sm_120 (their first-window
6.5 s and flashinfer JIT issues are young-stack problems); (3) a
hand-built CUDA-graph sub-talker (§8.3) if the platform ever owns a
GPU serving runtime. Kokoro's production posture is untouched by this
milestone.

## 21. Next milestone (Phase 24)

Per the C-branch: **the Qwen normal-TTS path is DEFERRED, not
closed.** No follow-on milestone is scheduled. The one cheap decisive
experiment left is hardware, not software: rent an RTX 5090/A100 hour,
run `m45prof.py` + `stream.py` unchanged, and read RTF. If RTF < 0.8
there, the M46 "Qwen GPU web prototype" question reopens with the
streaming layer already built and proven. Until then, English + Hindi
production remains Kokoro (M42 posture).
