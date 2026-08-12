# Milestone 15E — Qwen3-ASR Engine Adapter + Product-Path Evaluation: Close-Out Report

| | |
|---|---|
| **Status** | MILESTONE CLOSE-OUT — adapter built behind the existing engine seam; the candidate measured on the FULL frozen Hindi primary through the standard runner; **first positive model result in the program's ledger** |
| **Date** | 2026-08-12 (identity verification, adapter, all evaluations this date) |
| **Verdict, stated plainly** | On `stt-hi-public-eval@v1` (153 clips, same ruler, same harness, same decode-policy discipline as the official baseline): **CER 0.1457 vs 0.3629 — −60% relative, ~15× the 0.014 noise band — at RTF 0.21 vs 0.785, p95 3.3 s vs 24.2 s, 0 hallucinated probe words, 0 failures**, replicate within 0.0011 CER. English intact (WER 0.0). Chinese CER 0.1129. Peak RSS 1,363 MiB. |
| **Classification (Phase 15)** | **A. STRONG CANDIDATE** — with the production-readiness gaps in §14/§15 named, none of which is accuracy, speed, memory, hallucination, or license |

Labels: **[EVIDENCE]** committed EvalRun · **[FACT]** verified at source/recorded ·
**[SPIKE]** sandbox measurement · **[HYPOTHESIS]** untested explanation.

---

## 1. What was inspected

The engine seam (`TranscriptionEngine` protocol; `describe/transcribe/close`),
the slot catalog and its weightful-identity law, the artifact store
(pin-verify at boot), the evaluation runner (HTTP `/info` + `/v1/transcribe`,
artifact resolved from manifest, never operator-named), the research
manifest, EvalRun/ruler structures, and the 15B spike (method + artifacts).
Conclusion: the smallest adapter seam is **one engine module + one catalog
entry** — the architecture's own promise, now exercised by a non-Whisper
lineage for the first time. No evaluation-plane change of any kind.

## 2–3. Model identity and license [FACT, verified at source 2026-08-12]

| | |
|---|---|
| Served artifact | `qwen3-asr-0.6b@v1` = official ggml-org GGUF conversion, repo `ggml-org/Qwen3-ASR-0.6B-GGUF` @ revision `928ab958557df9aa2ef1c93e0e83c7ad0933fae2` |
| Files (pinned, verified against HF LFS metadata AND re-hashed locally) | `Qwen3-ASR-0.6B-Q8_0.gguf` sha256 `bca25981…` (805 MB) · `mmproj-Qwen3-ASR-0.6B-Q8_0.gguf` sha256 `41a342b5…` (214 MB) |
| Upstream model | `Qwen/Qwen3-ASR-0.6B` @ `5eb144179a02acc5e5ba31e748d22b0cf3e303b0` |
| License | **apache-2.0 on the 0.6B card itself** (the dossier's earlier verdict was read on the 1.7B card); not gated; **no custom .py files in the repo — no `trust_remote_code` surface** |
| Variant selection | 0.6B over 1.7B: the CPU-economics candidate (15B spike measured it; 1.7B has no CPU measurement); Q8_0 over bf16 GGUF: the quantization the spike validated, half the memory |

## 4–5. Runtime choice and dependency changes

**Serving path: the pinned llama.cpp b10344 CPU build's `llama-server`**
(zip sha256 `c0cec882…`, recorded since 15B), spawned as a loopback-only
child process per loaded slot, health-gated at load, killed at close.
Chosen over per-request CLI (pays model load per request — not a serving
measurement), llama-cpp-python (no audio support), and transformers
(unquantized, heavyweight new dependency, and it would measure a
different build than the only CPU path we have evidence for). The GGUF
card itself documents llama-server as the intended usage. **Python
dependency changes: none** — the adapter is stdlib-only (subprocess +
urllib to 127.0.0.1). Config: `INTELLIAI_STT_QWEN3_SERVER_BINARY`
(default: the spike's pinned build), `_CONTEXT_TOKENS` (4096 — the spike
proved default 32k allocates 8.2 GiB KV needlessly), request timeout.

## 6. Adapter architecture

`engines/qwen3_asr.py` (research-only, one `CATALOG` entry):
canonical PCM → minimal RIFF/WAV wrap → base64 `input_audio` →
`POST /v1/chat/completions` (greedy, temperature 0, max_tokens 2048) →
parse `language <Name><asr_text><transcript>` → contract
`TranscriptionResult` (detected-language tag mapped to ISO codes, the
request hint only filling gaps; one utterance-spanning segment, because
this lineage's ASR models emit no timestamps [FACT — the aligner is a
separate model covering 11 languages that exclude hi]). Empty output is
a *result* (probe semantics), transport/timeout/malformed failures are
contract errors. `describe()` reports the exact decode policy sent.
**Deliberate divergence from the 15B spike, recorded:** greedy decode
instead of CLI-default sampling (temp 0.8) — replicate stability is part
of the evaluation contract; the replicate's 0.0011 CER spread vindicates
it. 21 offline tests cover parsing, transport, identity, admission,
error shaping, timeouts, and leak hygiene — CI never touches the model.

## 7. Hindi benchmark result [EVIDENCE — the milestone's answer]

`stt-hi-public-eval@v1` (sha `cf643146…`, byte-identical, 151 natural
speaker-disjoint clips + 2 probes), research-harness route, standard
runner, port 8003:

| Metric | Whisper-small (official 15C baseline) | **Qwen3-ASR 0.6B** | Replicate |
|---|---|---|---|
| **cer_unicode** | 0.3629 | **0.1457** | 0.1446 |
| wer_unicode | 0.6590 | **0.2851** | 0.2851 |
| substitution_rate | 0.4764 | 0.2099 | 0.2081 |
| insertion_rate | 0.0328 | **0.0169** | 0.0181 |
| deletion_rate | 0.1498 | 0.0583 | 0.0589 |
| **hallucinated probe words** | 0 | **0** | 0 |
| recognition_rtf | 0.785 | **0.207** | 0.152 |
| inference p50 / p95 | 2.73 s / 24.2 s | **1.45 s / 3.32 s** | 1.06 s / 2.46 s |
| failures | 0/153 | 0/153 | 0/153 |

**Noise-band discussion (mandatory):** the improvement is −0.2172 CER —
**~15× the 0.014 band** — and the replicate lands 0.0011 from the
primary (greedy decode: the 15C engine-variance caveat largely
disappears). WER improves −57% with insertions HALF the incumbent's —
the exact axis every Whisper fine-tune failed on. The 15B spike's 30-clip
FLEURS reading (0.0796) moderated to 0.1457 on this harder,
spontaneous, speaker-disjoint corpus, as expected — and still beats the
incumbent by 60%.

## 8. Chinese result [EVIDENCE — secondary objective]

`stt-zh-fleurs-eval@v1` (frozen comparability manifest; contamination
`known_overlap` recorded at freeze; 100 natural clips + 2 probes):
**cer_unicode 0.1129** (primary metric for zh) · recognition_rtf 0.094
· p50 1.10 s / p95 2.15 s · 0 hallucinated probe words · 0 failures.
(`wer_unicode` 0.61 is the unsegmented-zh artifact documented since 15B
— whole sentences align as single "words"; cer_unicode is the ruler.)
The zh slot remains CPU-viable at product quality class.

## 9. CPU / RAM / load measurements [FACT]

| | Whisper-small int8 | Qwen3-ASR 0.6B Q8_0 |
|---|---|---|
| Artifact size on disk | 967 MB (float32 CT2; int8 at load) | **1,019 MB** (805 model + 214 mmproj) |
| Peak RSS (serving process) | ~1.5 GB class (published 1,477 MB) | **1,362.5 MiB** (identical idle/under-load — ctx-4096 KV pre-allocated; default 32k ctx would be 8.2 GiB, configurational) |
| Model load / warmup | 12–44 s observed across boots | **1,042 ms / 141 ms** |
| Hardware | Intel i9-13980HX class (24 threads), Windows 11 — same box as every prior measurement | same |
| Threads | faster-whisper defaults | llama.cpp defaults (recorded in run records via /info decode_params) |

## 10. Hallucination behavior [EVIDENCE]

0 probe words on hi silence + tone, en silence + tone, zh silence +
tone — **six probes, all silent**, engine-level (no VAD shield needed).
The LLM-decoder-on-silence risk flagged in the dossier's open questions
did not materialize under greedy decode on any measured probe.

## 11. Comparison against Whisper-small — the engineering trade

SMALL: same memory class, comparable disk. FAST: 4–5× lower RTF, p95
7× better. ACCURATE: −60% CER on the primary, −57% WER, probes clean.
COMMERCIAL: apache-2.0 verified. DEPLOYABLE: CPU-only, 1.4 GiB, 1 s
load — but see §14 for what deployment still requires. On the
small-model strategy's own five axes the candidate wins four outright
and ties memory.

## 12. Product-path verification [FACT]

Full chain proven live: IntelliAI request → registry-manifest
resolution (`research:qwen3-asr-0.6b`) → slot binding → adapter →
contract response. Explicit-hi, detection (no hint), English, silence
probe, tone probe — all correct shapes, correct languages, empty-text
probes; unsupported artifact pin answers 400 `invalid_input` with
`param=model` and no internal names in the message. `/info`
self-describes the full decode policy. Request logging flows through
the standard structured pipeline (artifact, media_format,
audio_seconds, total_ms per request).

## 13. E1c decode-mode diagnostic [SPIKE — arms compare to each other ONLY]

The E1b close-out's prime suspect — training labels in the
`<|notimestamps|>` regime vs timestamped product decode — was tested on
the failed E1b artifact itself (model.bin `806cfdb9…`, direct
faster-whisper, int8, first 30 frozen-primary clips + probes, one
variable changed):

| | Arm A (product decode) | Arm B (`without_timestamps=True`) |
|---|---|---|
| cer_unicode (char-weighted) | 0.7502 | **1.8958 — 2.5× WORSE** |
| insertion_rate | 0.5634 | **1.8514** |
| RTF | 2.85 | 4.39 |
| hallucinated probe words | 116 | 66 |

**Verdict: the hypothesis is REFUTED.** If timestamp-mode mismatch were
the mechanism, arm B would collapse the repetition loops; instead they
tripled. The adapter damaged sequence termination in BOTH decode modes
— trained-mode decoding is *worse* than the mismatched mode it was
blamed on. Consequence: no E1c retrain is indicated by this evidence;
the whisper-small LoRA r32/q+v recipe family is now dead on three
independently tested axes (schedule, checkpoint, decode mode), which
makes the fine-tuning pause a measured conclusion rather than a
judgment call. Record: `research/experiments/15e-qwen3-adapter/e1c-results.json`
(NOT ledger evidence; arm-vs-arm comparison only).

## 14. Risks

- **llama.cpp binary dependency**: the serving path requires a native
  binary outside the Python dependency tree. Research config points at
  the pinned local build; production would need a vendored, checksummed
  binary (or container layer) with its own supply-chain review.
- **No streaming; no timestamps for hi** [FACT]: `verbose_json`-style
  per-word/segment timing cannot be served for Hindi by this lineage
  today (the ForcedAligner covers 11 languages excluding hi). The
  adapter returns one utterance-spanning segment.
- **Concentration risk** (dossier §13): Qwen already backs several
  planned capabilities; FOUNDATION_MODELS §14 requires a warm non-Qwen
  alternative wherever Qwen is primary.
- **Licence watch triggers** stand: a non-Apache Qwen release
  precedent exists; geopolitical action on Chinese open weights.
- **Auto-context memory**: misconfigured ctx (llama.cpp default 32k)
  allocates 8.2 GiB — deployment must pin ctx; ours does.

## 15. Limitations

Single machine, single process, sequential requests — no concurrency
ladder yet (the existing bench harness can run one when a promotion is
actually proposed). zh measured on a contaminated-comparability corpus
(recorded at freeze), not a zh primary. No Arabic/Tamil/Malayalam
claims: ta/ml are absent from the official language list [FACT,
ledger 2026-08-11] — this lineage cannot serve those slots, ever.
30-minute-scale English set (4 clips) is a regression check, not an
English benchmark.

## 16. Decision classification

**A. STRONG CANDIDATE** — materially better accuracy (~15× noise band),
clean probes, RTF/latency in a better class than the serving SLO
requires, same memory class, apache-2.0, and a realistic (if not yet
productized) deployment path. Not promoted: promotion is a founder
decision under the switching-test law, and §14's items are real
engineering work.

## 17. Next milestone recommendation

**Milestone 16 = the Hindi switching test + productization plan for
the Qwen3 engine**: (a) vendored/containerized pinned llama.cpp build
with supply-chain review; (b) concurrency ladder on the bench harness
(1/5/10/20 workers) for capacity economics; (c) the formal switching
test against the incumbent under the roadmap's rules (incumbent has
now shown measured weakness on its own primary — the precondition the
roadmap demands); (d) decision on segment-granularity contract for hi
(single-span segments vs aligner-gap disclosure). Separately and
cheaply: extend the zh reading toward a zh primary if the zh slot is
being brought forward. Whisper E1-family fine-tuning stays paused.

---

## Reproducibility block [FACT]

Base: ggml-org GGUF @ `928ab958` (pins `bca25981…`/`41a342b5…`,
verified against HF LFS + local re-hash) · upstream
`Qwen/Qwen3-ASR-0.6B` @ `5eb14417…` apache-2.0 · runtime llama.cpp
b10344 win-cpu-x64 (zip sha `c0cec882…`) via `llama-server`, ctx 4096,
greedy, max_tokens 2048, prompt "Transcribe the audio." · eval manifests
`stt-hi-public-eval@v1` sha `cf643146…`, `stt-eval-seed@v2`,
`stt-zh-fleurs-eval@v1` sha `8fdbe098…` · rulers `cer_unicode` /
`unicode_generic@v2` (hi/zh), `wer_ascii` anchor (en) · records:
4 EvalRuns in the append-only ledger + `info-at-eval.json` +
`rss-eval-session.json` in `research/experiments/15e-qwen3-adapter/` ·
CPU Intel64 Family 6 Model 183 (24 threads), Windows 11 · git commit
recorded in the milestone's commit set.

*No production surface changed. No customer data touched. The candidate
remains `research:`-namespaced; every route to it lives in the research
manifest only. Promotion, if it comes, is a founder decision with a
switching test — exactly what the roadmap requires.*
