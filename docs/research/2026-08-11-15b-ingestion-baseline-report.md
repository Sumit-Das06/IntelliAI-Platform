# Milestone 15B — Public Dataset Ingestion + Frozen Evaluation: Decision Report

| | |
|---|---|
| **Status** | MILESTONE CLOSE-OUT — measurement foundation delivered; no training, no production change |
| **Date** | 2026-08-11 (all runs, license reads, and access checks performed this date) |
| **Delivers** | the first reproducible public-data manifests (frozen, hash-pinned), the first natural-speech Hindi baseline in the evaluation ledger, and the first CPU measurements of the Qwen3-ASR 0.6B candidate |
| **Governed by** | [RESEARCH_FRAMEWORK.md](RESEARCH_FRAMEWORK.md) · [STT_EVALUATION_SUCCESS_CRITERIA.md](STT_EVALUATION_SUCCESS_CRITERIA.md) · [2026-08-11-small-asr-model-strategy.md](2026-08-11-small-asr-model-strategy.md) |

Labels: **[EVIDENCE]** = committed EvalRun in the append-only ledger ·
**[SPIKE]** = research-sandbox measurement (no MeasurementRoute; may be
read beside EvalRuns, **never differenced** against them) · **[FACT]**
read at source, dated · **[BLOCKED]** a recorded refusal with reason.

---

## 1. Dataset sources and licenses

| Source | License [FACT, read at source 2026-08-11] | Access this session | Used |
|---|---|---|---|
| google/fleurs | CC-BY-4.0 | **OPEN** (`gated: false`) | ✅ hi test+train, zh test |
| ai4bharat/IndicVoices | CC-BY-4.0 | **[BLOCKED]** `gated: auto`, anonymous fetch 401, no HF token on machine | registered, adapter-ready |
| ai4bharat/Kathbath | CC0 (explicit waiver) | [BLOCKED] same | registered |
| ai4bharat/Lahaja | MIT (card tag; an earlier read said CC-BY-4.0 — both recorded) | [BLOCKED] same | registered |
| Common Voice 26.0 (hi, zh-CN) | CC0 + MDC terms (no re-hosting) | [BLOCKED] moved exclusively to Mozilla Data Collective; account required | registered |

The full registry (with unblock conditions) is code:
[`ml/datasets/src/intelliai_datasets/sources.py`](../../ml/datasets/src/intelliai_datasets/sources.py),
pinned by tests. **No license was assumed; blocked is a recorded status.**

## 2. Frozen manifests (the milestone's permanent artifacts)

| Manifest | Contents | Pin (SHA-256) |
|---|---|---|
| **`stt-hi-fleurs-eval@v1`** — [ml/evaluation/stt/datasets/stt-hi-fleurs-eval-v1.json](../../ml/evaluation/stt/datasets/stt-hi-fleurs-eval-v1.json) | 120 natural clips (1,409.6 s) + 2 probes carried byte-identical from seed v2; per-clip SHA-256 path sources | `5b2c8396e3a13511dfeb58af1c6f2bbfbfe6b8a872074015366b0ff8556b6d02` |
| **`hi-fleurs-train@v1`** — [ml/datasets/manifests/hi-fleurs-train-v1.jsonl](../../ml/datasets/manifests/hi-fleurs-train-v1.jsonl) | 2,115 samples, **6.61 h** (platform 5-field JSONL; content-hash-disjoint from the frozen eval, enforced by validation) | `93426dffa97b355a9676c1f1331f1b681decd0b26881501e1a41721a1a2ba3d6` |
| **`stt-zh-fleurs-eval@v1`** — [ml/evaluation/stt/datasets/stt-zh-fleurs-eval-v1.json](../../ml/evaluation/stt/datasets/stt-zh-fleurs-eval-v1.json) | 100 natural clips (1,229.5 s) + 2 zh probes | `8fdbe0986d5ec88de59b488327dbbf07c71acd47458ec6b4516e24afae50b7a0` |

**NORMALIZATION VERSION:** `unicode_generic@v2` (`hi` and, bound this
milestone, `zh`). **RULER VERSION:** `cer_unicode` primary (metric
registry v3); `wer_unicode` co-recorded (not meaningful for unsegmented
zh — recorded, never cited). Eval was frozen **before** the train
manifest was written; `freeze-train` requires the frozen eval as input,
so the ordering is enforced by tool shape, not discipline.

**Honest limitations of v1:** FLEURS publishes no speaker IDs, so
speaker-disjointness between train and eval is **unprovable** — it rests
on FLEURS's official split boundary (publisher claim). Contamination is
`known_overlap` (FLEURS sits in most public models' training mixes):
these are **comparability rulers**, not the product primary. The
approved primary (speaker-disjoint IndicVoices slice) builds the day the
HF gate is accepted — the adapters, validation (including speaker-roster
disjointness), and freeze tooling are all in place.

## 3. Validation results

418 + 2,120 + 945 candidates ingested (0 row problems after the
IEEE-float WAV fix); every rejection explicit and recorded in the
provenance sidecars: **6 duration bounds (>30 s), 1 duplicate-class** —
nothing silently discarded. Candidates = accepted + rejected on every
pass (pinned by test).

## 4. Whisper-small Hindi baseline — [EVIDENCE], the number to beat

Committed:
[ml/evaluation/stt/results/2026-08-11-intelliai-stt-hi-whisper-small-int8-15b-fleurs.json](../../ml/evaluation/stt/results/2026-08-11-intelliai-stt-hi-whisper-small-int8-15b-fleurs.json),
named baseline `2026-08-11-intelliai-stt-hi-whisper-small-int8-fleurs`.
Product path: `intelliai-stt`/`hi` resolved from the exported registry
manifest; fresh native runtime, port 8004; artifact `whisper-small@1`
(SHA-256-pinned files), faster-whisper 1.2.1, int8, CPU.

| Metric (120 natural clips, 3,042 ref words) | Value |
|---|---|
| **cer_unicode (primary)** | **0.2919** |
| wer_unicode | 0.5624 |
| substitution / insertion / deletion rates | 0.4119 / 0.0365 / 0.1141 |
| hallucinated_words (silence + tone probes) | **0** |
| recognition_rtf (duration-weighted) | **0.3474** |
| inference p50 / p95 | 2.64 s / 15.19 s |
| load / warm-up | 5,358 ms / 2,020 ms |
| failures | 0 / 122 |

Zero-shot whisper-small Hindi is now **measured** on our own ruler:
CER ≈ 0.29, WER ≈ 0.56. The anecdotal "Hindi wedge gap" is an anecdote
no longer. Real-speech Hindi RTF is 0.347 — the 9.4× declaration figure
was a non-speech artifact, now bounded.

## 5. Qwen3-ASR 0.6B GGUF — [SPIKE] (CPU, llama.cpp b10344, Q8_0)

Artifacts hash-verified against HF LFS pins (model `bca25981…`, mmproj
`41a342b5…`). Method, per-clip data, and environment:
[research/experiments/15b-qwen3-gguf-spike/](../../research/experiments/15b-qwen3-gguf-spike/).
Sandbox results — no MeasurementRoute, never differenced against
EvalRuns; the like-for-like reads below are side-by-side readings on
identical clips, offered as motivation for an adapter, not as a
switching-test result.

| | Hindi (first 30 frozen-eval clips) | Chinese (first 30 frozen-eval clips) |
|---|---|---|
| cer_unicode (char-weighted) | **0.0796** | **0.1313** |
| same-30-clips whisper-small mean CER [EVIDENCE-derived] | 0.2515 | (whisper zh unmeasured on our ruler) |
| net RTF (wall − load overhead) | 0.184 | 0.086 |
| gross RTF (incl. per-invocation model load) | 0.287 | 0.179 |
| **peak RSS, ctx=4096** | **1,515 MiB** | 1,513 MiB |
| peak RSS, llama.cpp default ctx | 8,238 MiB (32k-token KV allocation — configurational, not fundamental) | — |
| hallucination probes (silence, tone) | **0 words** | **0 words** |
| self-reported language tag | 30/30 "Hindi" | 30/30 "Chinese" |
| failures | 0 | 0 |

**The strategy-deciding readings:** on identical Hindi clips Qwen3-ASR
0.6B reads ≈**3.6× lower CER** than the serving incumbent, at roughly
**half the incumbent's compute** and, with a bounded context, **the same
memory class** (~1.5 GiB vs faster-whisper's published 1,477 MB). Both
probes silent. Chinese runs at RTF 0.086 — ~11× real-time on this CPU.
Caveats stated: 30-clip subsets; single process; contaminated
comparability corpus; Q8 quantization; the spike's serving shape
(single-shot CLI) is not a serving stack.

## 6. Blocked evaluations — recorded results [BLOCKED]

- **IndicConformer (600M multilingual + hi 120M):** two independent
  grounds, verified 2026-08-11 — (1) both repos `gated: auto`, anonymous
  fetch 401, no HF token; (2) the 600M card carries `custom_code` —
  `trust_remote_code` execution requires the security-review process
  (open prerequisite 5.3), which has not been ruled. Unblock: founder HF
  account + terms acceptance; then the security review before any
  in-process run.
- **Common Voice 26.0 zh-CN test (the approved zh eval):** MDC account
  required. The FLEURS-zh slice stood in, clearly labeled.
- **IndicVoices/Kathbath/Lahaja (the approved hi primaries):** same HF
  gate; ingestion adapters, speaker-disjoint validation, and freeze
  tooling are ready and tested — the unblock is a ~5-minute founder
  action.

## 7. Candidate comparison table (measured values only)

| Model | Language | CER | WER | RTF | p95 latency | Peak RAM | License | Status |
|---|---|---|---|---|---|---|---|---|
| whisper-small int8 (product path) | hi | **0.2919** | 0.5624 | 0.347 | 15.19 s | ~0.8 GiB steady (runtime) | Apache-2.0/MIT | **[EVIDENCE] — the named baseline** |
| Qwen3-ASR 0.6B Q8 GGUF ctx4096 | hi | **0.0796** | n/m | 0.184 net | n/m (single-shot CLI) | 1,515 MiB | Apache-2.0 | [SPIKE] — adapter-worthy |
| Qwen3-ASR 0.6B Q8 GGUF ctx4096 | zh | **0.1313** | n/m (unsegmented) | 0.086 net | n/m | 1,513 MiB | Apache-2.0 | [SPIKE] — zh slot viable on CPU |
| IndicConformer 600M / hi 120M | hi | — | — | — | — | — | MIT | **Evaluation blocked** (access + remote-code review) |
| whisper-small | zh | — | — | — | — | — | — | not measured (no zh product route; out of 15B scope) |

## 8. Reproducibility

Every number above is structured data: EvalRun JSON (dataset name@v +
manifest identity, artifact + version, engine + version, compute,
hardware line observed from the runtime, decode params, normalization
profile, per-clip metrics, determinations) in the append-only ledger;
spike JSON (manifest SHA-256, artifact SHA-256s, llama.cpp build + zip
SHA-256, prompt, context tokens, per-clip walls + hypotheses,
environment, method incl. overhead medians). Manifests pin every clip by
content hash; ingestion, validation, and curation are deterministic
(content-hash ordering; pinned by tests). Git commit hash accompanies
the milestone commit itself.

## 9. Recommendation for 15C/15D

1. **Unblock the primaries (founder, ~10 minutes total):** create an HF
   account, accept the AI4Bharat gates, provide a token; optionally an
   MDC account for Common Voice. Then 15C freezes the real
   speaker-disjoint `stt-hi-public-eval@v1` and re-baselines against it
   — everything is tooled.
2. **Proceed to E1 (15D) as designed** — the Hindi LoRA on whisper-small
   is still the right first *training* experiment: it proves the
   training loop end-to-end on the lineage we serve, on local hardware.
   The baseline it must move is now committed: **CER 0.2919**.
3. **Fund the Qwen3-ASR engine adapter as the next serving-side
   milestone** (was conditional; the spike converts it to
   evidence-justified): a proper engine behind the runtime contract
   (llama.cpp server or ONNX path), so Qwen3 can be measured on the
   product path, through the pool, with real latency percentiles — the
   only route to a legal switching test. Its Hindi and Chinese readings
   justify the engineering.
4. Keep IndicConformer blocked until the HF gate is accepted AND the
   remote-code security review is ruled; re-verdict then.

*Statuses unchanged in the ledger except dated evidence appends; no
model was promoted, no route changed, no training occurred.*
