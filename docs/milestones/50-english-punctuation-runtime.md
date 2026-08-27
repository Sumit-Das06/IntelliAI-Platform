# Milestone 50 — English Punctuation Runtime (kredor INT8 ONNX)

| | |
|---|---|
| **Status** | IMPLEMENTED, flag OFF everywhere — classification **A. ENGLISH PUNCTUATION READY FOR STAGING PROMOTION** (one recorded exception, §18) |
| **Date** | 2026-08-27 |
| **Model** | `kredor/punctuate-all` @ `0fe37019de3f5e4fbd83289fd94e07fa588e47df` (MIT), selected by M49 |
| **Runtime** | ONNX INT8 (weight-only dynamic quantization), artifact `punct-en-kredor@v1` |
| **Scope** | English punctuation stage inside the STT runtime, behind `INTELLIAI_STT_PUNCTUATION_EN_ENABLED` (default **FALSE**). No STT model change, no Hindi change, no UI redesign, no deployment. |
| **Evidence** | `research/experiments/50-english-punctuation-runtime/` (manifest + evidence/) |

## 1. Why (M49 hand-off)

M48 measured the IntelliAI-vs-Sarvam gap as **readability, not
recognition**: English ships no punctuation stage (M30 v1 is
Hindi-scoped). M49 selected `kredor/punctuate-all` (MIT; fp32 micro F1
0.674, boundary 0.827, 100% word-copy invariant) but its fp32 runtime
RSS was ~1489 MiB against a ≤700 MiB production target. M50's job:
convert to an efficient runtime, integrate behind a flag, prove every
gate.

## 2. Model identity (frozen)

- Source: `kredor/punctuate-all`, revision
  `0fe37019de3f5e4fbd83289fd94e07fa588e47df`, license MIT.
- fp32 weights sha256
  `9aec7aa51b4f8622be527ec668505d748932cdfb177a774f3f7fd204e01dcbae`.
- Label table `["0", ".", ",", "?", "-", ":"]` — recorded inside the
  hash-verified `provenance.json` so table and weights cannot drift
  apart (the M30 pattern). v1 mark scope: `. , ?` — `-` and `:` are
  DROPPED by decision, never silently emitted. `!` is not in the model's
  vocabulary (known and accepted at M49 selection).

## 3. Conversion (reproducible)

`torch.onnx.export` (opset 17) → `onnxruntime.quantization.quantize_dynamic`
(QInt8, **weight-only dynamic — no calibration set required**, documented).
Tools pinned: torch 2.11.0+cu128, transformers 4.57.3, onnxruntime 1.29.0,
Python 3.12.3 (2026-08-26, script `~/m50/convert.py`). fp32 reference
retained (WSL `~/m50/`, external-data layout). No untracked step.

## 4. Artifact `punct-en-kredor@v1`

| file | sha256 | bytes |
|---|---|---|
| `model.int8.onnx` | `b0d8d68ca907012e832282920c43ce8342c7920022ec9e9c125498de9478a925` | 277,964,353 |
| `sentencepiece.bpe.model` | `cfc8146abe2a0488e9e2a0c56de7952f7c11ab059eca145a0a727afce0db2865` | 5,069,051 |
| `provenance.json` | `bb74cc2440f342a69e3cbec427f7627769fd39abad6f7f1b3a1fbc72402374c3` | 1,429 |

Distribution is by SEEDING into the model volume (M30 law): the
ArtifactSpec's URLs are deliberately non-resolvable (`.invalid`), the
store hash-verifies every file at startup, and the restorer re-checks
the provenance hash at init. Missing/corrupt artifact on an ENABLED
deployment → startup refuses / readiness degrades (test-pinned). No
request-time download exists.

Tokenizer: the model repo ships no SPM file; the runtime uses the
pinned **xlm-roberta-base** SentencePiece model (kredor is an
xlm-roberta-base fine-tune, tokenizer unchanged) with the fairseq id
law `hf_id = spm_id + 1`, spm-unk→3 — **proven equivalent to the HF
tokenizer with 0 mismatches over all 1218 unique eval words**. The
forbidden `tokenizers` package was NOT added.

## 5. Conversion control (fp32 vs INT8, before integration)

Full frozen `en-punct-eval@v1` (120 rows) through both: **80/120 rows
byte-identical text**; corpus metrics within noise (INT8 micro 0.6814
vs fp32 0.6745; boundary 0.8142 vs 0.8270). Invariant: 0 failures both
sides. Verdict: conversion did not change the output contract.

## 6. Word-copy decoder

The M29B/M30 core is **imported, never duplicated**:
`apply_marks` (grew an `allowed:` marks parameter; Hindi call sites
unchanged), `invariant_holds`, `redistribute_segments`. The model only
votes on marks; original words are copied verbatim by construction,
and `restore()` still re-checks `invariant_holds` before returning.
Measured: **0 invariant failures** across 120 eval rows, 14 edge rows
(M16, pH, GMT, TMZ, URLs, emails, decimals, phone numbers, dates,
product names, code-like strings, Hindi words inside English), and
every long-transcript run.

## 7. Runtime wrapper

`EnPunctuationRestorer` (`engines/punctuation_en.py`): loads once at
startup, provenance hash re-check, onnxruntime CPU session +
SentencePiece, M49 windowing (180 words / 20 overlap / 510 pieces),
bounded inference via executor + timeout (default 3000 ms),
deterministic, no network/shell/dynamic download at request time.
**Every stage problem fails open to the raw transcript** — STT never
fails because punctuation failed.

## 8. Pipeline contract & provenance

audio → STT engine → raw transcript → English punctuation stage →
served transcript. The stage rides the SAME bounded worker slot after
the final transcript exists (post chunk-merge); silence short-circuits
before it. Contract (identical to M30): `text` = served (punctuated),
`raw_text` = original STT output (or `None` when no stage applied).
The gateway's collection service already stores `raw_text` as the
immutable `original_transcript`, so the chain **raw → punctuated →
human correction** holds, and with a failed stage `raw → correction`
still works (`apps/api/tests/test_punctuation_provenance.py`). No
public API change; no new fields — M30's additive contract reused.

## 9. Language gating

English stage: `en, en-US, en-IN` (route-resolved language, never a
client's "auto" — no language, no stage). Hindi keeps the existing M30
stage; at most one of the two stages ever applies. Service-level
proof: boss clip with `language=hi` → `punctuation_en: 0.0`, stage not
applied (`evidence/boss-audio-hi-gating.json`).

## 10. Feature flag

`INTELLIAI_STT_PUNCTUATION_EN_ENABLED`, default **FALSE** (the
existing `punctuation_enabled` convention). Guard tests pin the
default. Measured on the same boss audio through real service
instances:

- flag OFF → `text` **byte-for-byte identical** to the flag-ON run's
  `raw_text`; `raw_text` is `None`; no `punctuation_en` timing stage.
- flag ON → `text` punctuated, `raw_text` = original.

Turning the flag off is therefore a valid instant rollback. Production
stays OFF in M50 — no production route or config change shipped.

## 11. Memory gate (target ≤ 700 MiB) — PASS

Fresh-process measurement, INT8 artifact, CPUExecutionProvider
(`evidence/memory-gate.json`): baseline 39.3 → after load 393.8 →
after first request 418.3 → after 30 requests 436.8 MiB; **peak 568.5
MiB**. Load 748 ms. (M49 fp32 comparison point: ~1489 MiB → INT8 cuts
~2.6×.)

## 12. Latency gate — PASS

Warm p50/p95 ms over 15 runs (`evidence/latency-ladder.json`); cold
first inference (300 words) 59 ms:

| input | p50 | p95 |
|---|---|---|
| 1 sentence (9 w) | 4.7 | 4.9 |
| 3 sentences (40 w) | 10.3 | 12.1 |
| 100 words | 18.5 | 19.1 |
| 300 words | 54.3 | 55.7 |
| 700 words | 122.5 | 126.9 |
| 1200 words | 212.8 | 217.4 |
| 2000 words | 360.4 | 373.0 |

Proposed gate "punctuation p95 ≤ 10% of STT p50" (still PROPOSED, not
relaxed): on the real 102 s boss clip the stage took **45.2 ms**
against 8031 ms inference in the same request (**0.56%**), and against
M48's STT p50 of 6.37 s it is **0.7%** — pass with ~14× headroom.

## 13. Quality gate (frozen `en-punct-eval@v1` through the SHIPPED stage) — PASS

Ruler `punct_slots@v1`, 120/120 rows aligned, **0 invariant
failures**, 0 fail-open events (`evidence/quality-shipped-stage.json`):

| metric | M49 fp32 | M50 shipped INT8 |
|---|---|---|
| micro F1 | 0.6745 | **0.6814** |
| boundary F1 | 0.8270 | 0.8142 |
| comma F1 | 0.5570 | 0.5674 |
| question F1 | 0.8235 | 0.8889 |
| period F1 | — | 0.7942 |
| spontaneous micro/boundary | 0.639 / 0.727 | 0.588 / 0.647 |

Micro, comma and question improved; boundary −1.3 pt and the (small,
LOW-CONFIDENCE 3-row) spontaneous slice dipped — the same numbers the
standalone INT8 model produced in conversion control, i.e. **runtime
integration changed nothing**. No material regression. Exclamation:
not in the model vocabulary, F1 0 on both sides (accepted at M49).

## 14. Boss audio (same 102 s clip, sha `117cba69…af635`) — before/after

Real pipeline, real service (`evidence/boss-audio-punctuated.json`;
audio itself never enters git). Stage cost 45.2 ms. Excerpt, actual
output:

RAW:
> "see this is a text to which I generated from my speech okay and if
> you see it has taken the whole statement or speech as one statement
> so that's where we need to add punctuations and signs …"

PUNCTUATED:
> "see, this is a text to which I generated from my speech okay, and
> if you see it has taken the whole statement or speech as one
> statement. so that's where we need to add punctuations and signs. …"

Every word verbatim (invariant holds); sentence boundaries and commas
now exist. Against the captured Sarvam output the comparison stays
**QUALITATIVE ONLY** (M48 directive; no Sarvam metrics anywhere): the
readability gap M48 classified — "IntelliAI output is one unbroken
run-on" — is closed in kind; capitalization remains out of v1 scope.

## 15. Long transcripts — PASS

`evidence/long-transcripts.json` (~150 spoken words/min equivalents):
75 w → 19 ms, 300 w → 56 ms, 750 w → 142 ms, 1500 w (≈10 min speech) →
**261 ms**; every run zero truncation / deletion / insertion /
duplication (word-for-word depunct equality, equal word counts).

## 16. Streaming / response-mode interaction (Option A, documented)

The product path is single-shot: STT completes → punctuation runs on
the same worker slot → ONE response carries both `text` (punctuated)
and `raw_text` (raw). Raw-ready and punctuated-ready are the same
moment; the delta is the stage time itself (45 ms on the boss clip).
**No streaming punctuation is claimed — none is implemented.**

## 17. Fail-open & failure battery — PASS

Unit tests (19, `test_punctuation_en_stage.py`) cover missing model,
corrupted artifact, timeout, tokenizer error, inference exception,
malformed prediction (label outside the pinned table). Service-level
proof: an instance forced to a 0.001 ms stage timeout returned **HTTP
200 with the raw transcript**, no client-visible error, stage cost
4.1 ms (`evidence/boss-audio-failopen-timeout.json`). Enabled
deployment with unseeded artifact refuses startup (M30 law,
test-pinned); readiness reports `punctuation_en: ready|disabled`.

## 18. Regression & E2E

- **English**: raw path byte-identical (flag OFF `text` == flag ON
  `raw_text`), so WER/CER are definitionally unchanged; silence
  short-circuits before the stage; long-audio path untouched.
- **Hindi**: M30 stage code untouched (only `apply_marks` gained a
  defaulted parameter; Hindi call sites and `SUPPORTED_MARKS`
  unchanged); Hindi suite green; service-level `language=hi` never
  runs the English stage.
- **Full battery**: stt-runtime 224 passed / 1 skipped; full workspace
  `make test`, lint, mypy strict — green (commit gate).
- **Web/UI**: no UI change shipped. The console displays `text`, and
  Copy/Share/Correction operate on the displayed transcript
  (M46/M47 test-pinned); the gateway provenance contract is
  test-pinned. **Recorded exception:** the live-browser click-through
  could not run on this laptop without touching the frozen boss-demo
  docker stack (gateway is Postgres-only; the compose stack is the
  demo). It is gate #1 of the staging-promotion milestone.

## 19. Security

Local artifact only; request-time download impossible (`.invalid`
URLs, seeded volume); no shell interpolation; no dynamic file paths;
fail-open logs are server-side only (`punctuation_en_stage_failed` +
exception class, no text content); no model name, artifact hash or
internal path in any public error or console surface (internal names
law upheld — readiness says only `punctuation_en`, never "kredor").

## 20. Rollback

Three independent levels: (1) flag off — instant, per-deployment;
(2) artifact unseed — enabled deployment refuses to start (loud);
(3) `git revert` of the M50 commits — the stage is additive, no
schema/API migration to unwind.

## 21. Final classification

**A. ENGLISH PUNCTUATION READY FOR STAGING PROMOTION**

- word invariant **100%** (0 failures everywhere) — PASS
- quality within M49 gate (micro/comma/question ≥ fp32; boundary
  −1.3 pt, same as standalone INT8) — PASS
- memory peak 568.5 MiB ≤ 700 — PASS
- latency 0.56–0.7% of STT p50 (gate ≤10%) — PASS
- long transcripts, fail-open, English regression, Hindi regression,
  artifact provenance, flag OFF in production — PASS
- browser E2E: contract + real-service level PASS; live-browser
  click-through deferred (demo freeze) — the recorded exception above,
  first gate of the next milestone.

| verdict | |
|---|---|
| MODEL | kredor/punctuate-all @ 0fe3701 |
| RUNTIME | ONNX INT8 (dynamic, weight-only) |
| WORD INVARIANT | **PASS** (100%) |
| QUALITY | **PASS** |
| MEMORY | **PASS** (568.5 ≤ 700 MiB) |
| LATENCY | **PASS** (≤0.7% of STT p50) |
| LONG TEXT | **PASS** |
| FAIL-OPEN | **PASS** |
| ENGLISH REGRESSION | **PASS** |
| HINDI REGRESSION | **PASS** |
| WEB E2E | **PASS (contract + service level; live browser deferred — demo freeze)** |
| PRODUCTION ENABLED | **NO** |

## 22. Next milestone (proposed, not started)

**English punctuation staging promotion**: enable the flag on the
local/staging stack after the demo freeze lifts, run the live-browser
E2E battery (boss audio, question/exclamation, numbers, names,
paragraph, long transcript; Copy/Share/Correct on the displayed
transcript), then the production promotion decision with its own
gates. Nothing auto-continues.
