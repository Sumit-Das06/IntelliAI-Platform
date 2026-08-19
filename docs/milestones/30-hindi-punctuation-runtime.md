# Milestone 30 — Hindi Punctuation Runtime Implementation

| | |
|---|---|
| **Status** | IMPLEMENTED + STAGED — capability live in the local production-shaped stack; **PRODUCTION DISABLED (explicit, guarded) pending its own promotion decision** |
| **Date** | 2026-08-19 |
| **Decision basis** | founder-approved revised gates (M29C) |
| **Evidence** | `research/experiments/30-punctuation-runtime/` |

## 1. Approved architecture (implemented exactly)

```
Client → /v1/audio/transcriptions → auth → validation → registry
  → STT runtime
      hi → Qwen E3 → direct ≤120s | chunk+merge 120–600s
                        ↓ FINAL MERGED RAW TEXT
                  punctuation restorer (predict marks only)
                        ↓
                  WORD-COPY DECODER (input words verbatim + marks)
                        ↓
                  invariant gate (fail-open → raw)
      en → Whisper (stage bypassed; existing behavior untouched)
  → API (text = final) → Web / Android / iOS (zero client changes)
```

Punctuation runs ONCE, after the final chunk merge, inside the same
admission pool slot — never per chunk; the M19 chunk/merge law is
untouched (VERIFIED: `merge_chunk_text` and every window constant
unchanged; the 205-test runtime suite still green).

## 2. Model identity (pinned, seeded, verified)

Artifact `punct-cap-seg-47@v1` (internal name; never on a public
surface): ONNX `640d91c0…0df4`, sentencepiece `1bc15b6e…af47`, config
`30eb8e05…5b84f2`; source repo revision `1b9d51fc…ba28`, Apache-2.0
(dossier: `docs/research/models/punct-cap-seg-dossier.md`). URLs are
deliberately non-resolvable — distribution is SEEDING
(`make staging-seed-models`), the store hash-verifies at every startup
(observed in the staging container log: `artifact_verified
punct-cap-seg-47 v1`), and an ENABLED deployment with missing/mishashed
files refuses to start. No downloads, no mutable references, no remote
execution at inference time.

## 3. Word-copy decoder + invariant (the safety core)

`services/stt-runtime/src/intelliai_stt_runtime/engines/punctuation.py`
— vendored onnxruntime+sentencepiece wrapper (the prototype `punctuators`
package is NOT a runtime dependency). The model returns argmaxed label
ids; the wrapper maps them through a pinned label table (proven against
the config hash at load) and ONLY ever appends v1 marks {।, ",", ?} to
the ORIGINAL whitespace tokens (`apply_marks`). "!" does not exist in
the model's label space and "." is out of v1 scope — both are dropped,
never invented. `depunct(output) == depunct(input)` holds by
construction and is still asserted per request; segments are rebuilt by
word-count redistribution so the verbose_json join law survives with
timings untouched.

## 4. Runtime location + config

Stage wiring: `api/routes.py::_ingest_and_transcribe` (post-engine,
same pool slot; timing surfaces as the additive `punctuation` stage
key); instance built once per process in the lifespan. Config
(`INTELLIAI_STT_` prefix, repo convention — the spec's
`INTELLAI_PUNCTUATION_*` naming adapted):

| Variable | Default | Law |
|---|---|---|
| `INTELLIAI_STT_PUNCTUATION_ENABLED` | `false` | OFF everywhere; prod overlay pins `"false"` explicitly; local-prod is the only committed enabler |
| `INTELLIAI_STT_PUNCTUATION_LANGUAGES` | `hi,hi-IN` | gate on the ROUTE-RESOLVED language; auto (no language) never triggers the stage |
| `INTELLIAI_STT_PUNCTUATION_TIMEOUT_MS` | `3000` | request-time safety net (measured 600 s tier ≈ 0.45 s) |

## 5. Fail-open behavior

Any stage problem — load failure at request time, inference failure,
malformed prediction (label id outside the pinned table), decoder
refusal, invariant violation, timeout — yields the RAW transcript on the
same 200; the diagnostic is one internal structlog event
(`punctuation_stage_failed`, exception CLASS only). Deployment problems
are the opposite of silent: an enabled runtime without verified
artifacts refuses to start, and preflight §4c catches it earlier.
Customer-visible surfaces never carry model/file/engine vocabulary
(existing leak suites all green).

## 6. Speech Sample provenance + correction

Contract v1 gained the additive `TranscriptionResult.raw_text`
(ADR-0016; None when no stage changed anything). The gateway stores
`original_transcript` = RAW ASR (immutable, the flywheel's ground
truth), `current_transcript` starts as WHAT WAS SERVED (the reworded
birth law — no stage ⇒ unchanged pre-M30 behavior), and appends a
`punctuated` event (public: name+time only; detail carries the
product-safe `hi-punct-v1`). Correction then evolves `current` exactly
as before: raw ASR → punctuated → human corrected, nothing lost —
test-pinned in `apps/api/tests/test_punctuation_provenance.py`.

## 7. ASR non-regression (Phase 20 HARD gate) — **PASS, MEASURED**

Frozen `stt-hi-public-eval@v1` against the SAME runtime build, stage OFF
vs ON (`asr-punct-off.json` / `asr-punct-on.json`,
`asr-nonregression.json`):

- Every ACCURACY metric **byte-identical** (CER 0.11612, WER 0.24064 —
  also byte-identical to the committed M23 record); `recognition_rtf`
  is wall-clock and excluded by documented design (Δ +0.019).
- Per clip: **153/153 word streams identical** after depunct; **0**
  non-v1-mark changes; 150/153 clips received marks (440 total).

## 8. Punctuation quality (Phase 21) — approved gates through the SHIPPING wrapper — **ALL PASS, MEASURED**

`hi-punct-eval@v3` + probe sets via `PunctuationRestorer`
(`quality-gates.json`):

| Approved gate | Measured | Verdict |
|---|---|---|
| word invariant = 100% | 100% on every slice; edges 0/22 corrupted | **PASS** |
| lexically-cued questions ≥ 85% | 91.3% | **PASS** |
| statement false positives = 0 | 0/12 | **PASS** |
| boundary F1 ≥ 0.70 (multi-sentence) | 0.7441 read-paragraph / 0.7222 ratified-51 | **PASS** |
| boundary F1 ≥ rules + 0.25 | 0.7441 vs 0.4216 (+0.33) | **PASS** |
| comma F1 ≥ 0.30 | 0.389 / 0.433 | **PASS** |

The 9 audio-flagged spontaneous rows remain informational/outside the
gate-bearing slice — **no audio/native review has happened yet** and
none is claimed (Phase 22).

## 9. Long audio, metering, silence

- ≤120 s direct and 120–600 s chunk+merge feed the stage ONCE with the
  final text; >600 s stays the loud 400; no chunk-size/overlap/deadline
  change anywhere.
- Metering: audio-seconds only — the provenance suite pins exactly one
  usage event for a punctuated request; stage failure bills nothing
  extra; text length is never a quantity.
- Silence short-circuits BEFORE the stage (empty text never meets the
  model) — pinned at route level and drilled in staging.

## 10. Performance (Phase 6) — development machine, NOT an SLA

`perf-runtime.json` (production wrapper, MEASURED): warm-disk load
0.58 s; tiers 5s→0.010 s · 30s→0.019 s · 120s→0.055 s · 300s→0.142 s ·
600s→0.267 s (best of 3); RSS peak 436.8 MiB (≤700 target); 4-way
concurrent 30 s burst through the shared session: 0.051 s total.

Target check: punctuation p95 ≤ 10% of STT p50 — the 30 s dictation
tier costs ~0.03 s against a ~9 s product-path STT p50 (M25 real
sessions): **~0.3%, PASS on this box**. Deploy-box re-ladder remains a
precondition for production enablement (UNKNOWN until then).

## 11. Staging battery (Phase 19) — production-shaped stack, Caddy edge

`staging-battery.json`: **22/22 PASS** — hi punctuated end-to-end
("क्या क्या चीज़ें लेना है हाँ।"); en bypass keeps whisper's own style
(no danda); auto (no language) takes the default route, stage never
fires; tiers 5/30/120/300/600 s all punctuated (600 s: 183 enders, wall
168 s); 300 s verbose_json **join law holds with punctuation** (4
segments); >600 s stays 400; digital silence and quiet noise stay
EMPTY; the question clip arrives with "?" through the whole stack
("क्या आप सुईजी से बात कर रहे हैं?"); contribution ON collects / OFF
skips; correction 200 on a punctuated sample; web(webm)/android/iOS
contract shapes all punctuated with android == iOS byte-identical;
runtime restart recovers with the stage intact; and the
disable/rollback drill (flag off via overlay) serves RAW text on the
same route — config-only rollback proven live.

Client note (honest): Web/Android/iOS were exercised as EXACT contract
shapes (headers, webm/wav bodies) against the live stack; no Android
device/JDK and no Mac exist in this environment, so the client TEST
SUITES are unchanged-and-not-rerun here — and M30 changed zero client
code (`apps/keyboard-android`, `apps/keyboard-ios`, console JS
untouched except the additive `Punctuated` timeline label).

## 12. Tests + CI (Phase 26)

Runtime 205 (+19 new stage tests incl. real-model laws) · contract 46
(+raw_text) · api 629 (+3 provenance, +3 ops guards) · evaluation 677 ·
datasets 81 · training 17 — all green; ruff + format clean; mypy strict
clean (329 files); `sentencepiece` added to the engine-isolation
denylist (guard strengthened). CI: §CI§

## 13. Security / privacy (Phase 23)

Transcripts never leave the infrastructure (in-process ONNX; no external
API; no new outbound flow); no temporary transcript files; artifacts
hash-verified; no secrets touched; leak suites green; the `punctuated`
event exposes name+timestamp only.

## 14. Production status (Phase 25)

    PUNCTUATION CAPABILITY IMPLEMENTED: YES
    LOCAL/STAGING VERIFIED:            YES (battery above)
    PRODUCTION ENABLED:                NO — `INTELLIAI_STT_PUNCTUATION_ENABLED: "false"`
                                       pinned in prod.yml + guard test
    HOSTINGER DEPLOYED:                NO

Activation is a separate promotion decision; its preconditions: deploy-
box re-ladder, founder call on the audio-flagged rows, and the standard
reviewed-commit flip of the prod overlay flag (rollback = flip back).

## 15. Next step

Production punctuation promotion (founder-gated), riding the eventual
Hostinger deployment milestone: seed `punct-cap-seg-47` on the box
(preflight §4c already enforces it when enabled), re-ladder, flip the
flag in a reviewed commit, canary per the M24 playbook.
