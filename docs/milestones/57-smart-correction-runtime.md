# Milestone 57 — Smart Transcript Correction Runtime (Staging Only)

| | |
|---|---|
| **Status** | IMPLEMENTED on LOCAL/STAGING — decision **A. SMART CORRECTION READY FOR STAGING** (recorded edges below, honest). **PRODUCTION: OFF** — flag pinned false + empty URL in prod.yml, ops-guard-tested. |
| **Date** | 2026-09-02 |
| **Model** | Qwen3-4B-Instruct-2507 Q4_K_M (Apache-2.0), GGUF sha `3605803b…`, on the pinned llama.cpp b10344 CUDA build — its OWN instance (:8802), never the realtime one. Fallback documented: Qwen3-1.7B. |
| **Evidence** | `research/experiments/57-smart-correction-runtime/` (29 files) |

## 1-4. Architecture (REPO-VERIFIED)

```
final transcript (batch or realtime) → punctuation (unchanged, guaranteed)
  → user clicks ✨ Improve → gateway POST /v1/text/corrections (auth first)
  → stt-runtime /v1/correct (flag-gated) → pinned correction llama-server
  → OUTPUT VALIDATION gate → improved text → Original/AI toggle → edit/Share/Copy/Save
```

- **Feature flag** `INTELLIAI_STT_SMART_CORRECTION_ENABLED` — default
  FALSE, staging true (local-prod), production pinned false with empty
  URL; flag off = no model, no endpoint activity, transcript path
  byte-identical (drilled, §11).
- **Artifact governance**: the launcher refuses drift on the llama
  binaries AND the GGUF; enabled-but-unreachable refuses startup;
  readiness answers `smart_correction: disabled|ready|degraded` with
  no model names/hashes/paths.
- The browser never touches the llama server (auth'd application
  endpoint only); every token stays local — no external AI service,
  no transcript content in logs.

## 5-6. Prompts + the two contracts (REPO-VERIFIED)

The M56 winning LANGUAGE-SCOPED prompt pair ships in code (a combined
prompt measurably caused EN→HI translation flips; scoping removed them).
Two contracts now stand side by side, both documented in code and pinned
by tests: **punctuation — words MUST NOT change** (word-copy invariant,
unchanged); **smart correction — words MAY change, meaning MUST NOT**
(prompt + mechanical validation gate).

## 7. Provenance (REPO-VERIFIED + tested)

`raw → punctuated → AI corrected → user corrected`, nothing collapsed:
raw/original stays immutable (existing law); an AI suggestion tied to a
collected sample lands as its OWN append-only `ai_correction_suggested`
event — `current_transcript` moves only when a HUMAN saves (existing
`corrected` event) — machine and human corrections are permanently
distinguishable (integration-tested against the real DB).

## 8-12. Realtime interaction, async, versioning (MEASURED)

Partials are NEVER corrected; Improve is a user action on the FINAL.
The browser is the async layer: the final shows immediately, "✨
Improving…" runs in the background (long Hindi ~9 s never blocks
reading/editing), and a **client-side transcript version counter makes
any in-flight result STALE the moment the user edits — proven in the
browser drill: the user's edit survived, the AI result was discarded
with a visible note.** States: idle → improving → applied/stale/failed,
all user-friendly copy, no internals.

## 13-18. UX, Copy, Share, human edit (MEASURED in real browsers)

One lightweight action (✨ Improve) beside Share — no page redesign; on
success an **Original / AI improved** toggle appears (the Phase-47
review mechanism); the textarea stays editable (AI is never
authoritative); Copy/Share/Save operate on the DISPLAYED text (browser
drill: Share clipboard == improved text when improved is active).
Correction save flow unchanged — the user's final version is what
`Save correction` stores, as before.

## Quality (Phases 19-24, MEASURED live through the gateway)

- **English**: every spec case correct (grammar/tense/articles/
  repetition); already-correct returned unchanged; hallucination-bait
  returned unchanged; 145-400 ms.
- **Hindi**: the spec's own Roman-Hindi example verbatim → "मुझे कल
  ऑफिस जाना था लेकिन मैं नहीं जा सका।"; Hinglish natural; already-correct
  unchanged. **Recorded miss**: one gender-agreement case got danda
  only (under-correction — the safe failure direction).
- **Protected entities, all preserved live**: Sumit, IntelliAI,
  QwikCart, Kubernetes, ₹12,500, 12 August 2026, +91-9876543210,
  test@example.com, example.com, version 2.5.
- **Ambiguity**: "i need to meat tomorrow" → "meet" (context-supported);
  the Original/AI toggle is the human-review path.

## Output validation — the trust gate (Phase 25-26, unit-pinned)

Before ANY AI output is served: non-empty · length ratio ≤2.5× · script
matches the session language (flip rejection BOTH ways) · digit runs,
emails, URLs from the input must survive verbatim · runaway repetition
rejected (the M54 guard reused) · prompt leakage rejected. A validation
failure is a friendly error and the punctuated transcript stands —
**the LLM is never blindly trusted.** Input ceiling 600 words; token
budget scales with input (never an arbitrary huge max_tokens); longer
inputs get an honest "too long" refusal (blind chunking stays rejected
per M56 measurement).

## Latency, GPU, scheduling (Phases 28-30, MEASURED)

Full-stack p50: EN 0.32/0.66/0.65/2.4 s and HI 0.97/2.2/4.8/8.9 s at
20/50/100/250 words — integration overhead over M56 is negligible.
VRAM: realtime stack + correction 4B = **5.9 GB total on the 8 GB
card**. Separate llama instances isolate queues, not GPU compute: a
worst-case CONTINUOUS correction hammer degrades realtime cadence
~1.7× (documented; real usage is one user-triggered job) — production
policy PROPOSED: cap concurrent corrections per realtime GPU.

## Fail-open, failure, rollback (Phases 32-33, 40-41 — drilled LIVE)

Correction server killed → friendly "AI correction is not available
right now. Your transcript is unaffected." + readiness `degraded` +
batch untouched → relaunch → `ready` and serving. Flag off → readiness
`disabled`, endpoint friendly 503, **batch boss30 byte-identical across
flag states (sha `b23ec9df…` both)**. STT/realtime/punctuation code
paths untouched by this milestone.

## Verification roll-up

17 new runtime unit tests (validation gate, scoping, health, route) +
5 gateway integration tests (auth, provenance event, fail-open,
passthrough) + console guard test + 2 ops guards; browser E2E EN+HI
(improve/toggle/share/stale/leak-scan clean) + mobile 390/820/desktop;
realtime regression measured; batch byte-identity proven; full
workspace suite green; lint + mypy clean.

## Decision + next milestone

**A. SMART CORRECTION READY FOR STAGING.** Recorded edges: HI
under-correction on one live gender case; HI >50-word latency
(async UX covers it); worst-case GPU contention policy proposed, not
enforced in code. **Next (ONE, founder-gated): Smart Correction staging
hardening + founder review** — founder plays with the staging feature,
the HI edge cases and the correction-concurrency cap get hardened, and
the production-promotion question follows the established path.
**PRODUCTION SMART CORRECTION: OFF. HOSTINGER: untouched.**
