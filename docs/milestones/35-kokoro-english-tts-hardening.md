# Milestone 35 — Kokoro English TTS Hardening + Local Web End-to-End

| | |
|---|---|
| **Status** | COMPLETE — every M33 defect fixed and regression-proven; the first real Web TTS client verified end to end on the production-shaped local stack |
| **Date** | 2026-08-20 |
| **Decision base** | M33 ("keep Kokoro — and harden it") + M34 (Qwen3-TTS spike lost on measurement) |
| **Evidence** | `research/experiments/35-kokoro-hardening/evidence/` · guard tests across `services/tts-runtime/tests`, `apps/api/tests` |

    TTS IMPLEMENTED: YES        (hardened runtime v0.2.0, live-verified)
    WEB E2E VERIFIED: YES       (Speech Studio through the HTTPS edge; see §13)
    PRODUCTION DEPLOYED: NO
    HOSTINGER: NO

## 1. Where this started (M33's measured defects)

Incumbent trap-set RT-WER 0.1247 — OOV word-drops ("Hello, Sumit." →
"Hello."); no text normalization (₹ dropped, slash-dates spelled); TTFA
= whole body; a dormant dual-unit billing bug; a live stale-image trap;
placeholder voice names; and no Web client at all. The research twin
(Kokoro + espeak fallback) measured 0.0716 — the target this milestone
had to reach through the PRODUCTION path.

## 2-3. OOV fix — the espeak subprocess boundary (policy gate: CLOSED, recorded)

**The GPL policy gate is closed, not silently assumed**: the M3 design
review §8 (founder-approved) named the exec-boundary shape defensible
("GPL-clean the way ffmpeg is") and reserved it for exactly this use;
the M35 spec (Phase 2) directed the implementation through "the
repository's approved GPL-binary posture". Recorded posture: the
espeak-ng BINARY ships in the image via apt and runs as a
**subprocess** — constant argv, words via stdin, UTF-8 pinned, 2 s
timeout, absolute pinned path, version-prefix pin (`1.5`) that refuses
startup on mismatch, fail-open to dictionary-only per chunk. The GPL
*python* chain (phonemizer-fork/espeakng-loader) **stays banned
in-process**: the poison stub, the build-fatal uninstall check, and the
isolation suite are all unchanged.

Mechanics: misaki marks unknowns (`phonemes=None` or embedded `❓`);
unknown tokens are batched to one espeak call per chunk and spliced back
in token order through the vendored espeak-IPA→Kokoro mapping (adapted
from misaki, Apache-2.0; the M32 parity probe measured the transform
classes). Counts are logged, never the words (customer-owned text).

## 4. Text normalization v1 (the pipeline seam, occupied)

Deterministic, idempotent, speech-only rules — currency ($X.YY, ₹N,NNN
incl. paise), percent, DD/MM/YYYY slash-dates (documented Indian
convention), phone-style digit groups (+CC and 3-5-digit groups →
digits spoken). Everything else passes byte-identical (names, plain
numbers, spoken dates — test-pinned). **Provenance law**: the original
text remains the billing fact (characters counted on request text) and
the only text the gateway ever stores/logs; the normalized form exists
only between pipeline and engine. Kill-switch:
`INTELLIAI_TTS_NORMALIZE_TEXT` (default on).

## 5. Billing — characters only, telemetry preserved

`quantities={characters}` on the synthesis ledger row;
`measured_audio_seconds` moves to the lineage side (metered, never
rated). Pinned by `test_tts_billing.py`: 1000 chars → exactly 1000
rated units and a characters-only invoice line (with the counterfactual
asserted: `audio_seconds` IS priced in the book — its absence from the
row is what prevents the double charge); same text at three speeds
bills identically; failures and refusals bill nothing.

## 6. Chunking / TTFA

Sentence chunks now MERGE up to the 300-char budget (the M3 debt: two
short sentences used to cost two ~500 ms model passes). The engine
records `first_chunk` timing into the envelope stages — the telemetry
that prices the future streaming decision — while the HTTP response
stays whole-body (ADR-0020 remains chunk-ready; no contract change).

## 7. Long text law

2000 characters, enforced before any engine runs, documented in the
public schema description and the Studio UI ("refused, never cut
short"); over-limit is a clean `invalid_input` (battery-verified 400).

## 8. Stale-image protection

`/info` (internal port) now reports `service_version`, `normalization`,
`oov_fallback`, `max_text_chars`; version bumped to **0.2.0**.
`infra/tts-smoke.sh` (+ `make tts-smoke`) fails a stack whose running
code is older than the floor, whose loaded artifact is not the declared
one, whose posture keys are missing/mismatched, or whose gateway cannot
return real WAV — the M32 "healthy, and wrong" trap is now mechanically
catchable. Guard-tested in `test_ops_configuration.py`.

## 9. Artifact pinning

Unchanged and re-verified: 4 SHA-256-pinned kokoro files re-hashed
every boot; misaki's spaCy asset is a hash-locked wheel; the espeak
binary is version-pinned at engine load (wrong version = loud startup
refusal when the fallback is enabled); no request-time downloads
anywhere; missing files fail readiness.

## 10. Voice naming

Launch names **`english-female` / `english-male`** (product-friendly,
neutral, no proprietary-voice claim); `reference-alto`/`reference-bass`
remain served forever as legacy aliases (voice ids are permanent API
surface — renaming is addition, never removal; alias-identity is
test-pinned: same engine reference behind both names). Engine tokens
(`af_*`…) remain banned from every public surface.

## 11-12. Web API + Web UI

API: the EXISTING `POST /v1/audio/speech` — no new endpoint; schema
descriptions now document the voices, the 2000-char law, and the
billing unit. UI: **Speech Studio** at `/console/speech` (nav entry +
services-card link): textarea with live counter, voice selector
(English Female/Male), speed (0.75/1/1.25), Generate, `<audio>` player,
Stop, Download WAV — with friendly words for every failure state
(empty, over-limit, 401, 429, runtime-down, server error; never an
endless spinner). The card badge stays **"Coming Soon"** — a badge is a
LAUNCH claim and TTS has not launched; a link is page availability
(soon+href = "preview available, no promise" — documented at the data
source and test-pinned). No engine vocabulary anywhere (leak sweep
extended: kokoro/espeak/af_/am_ banned on all console surfaces).

## 13. Local Web end-to-end — VERIFIED (production-shaped stack, HTTPS edge)

`make local-prod-up` now serves TTS in the production-shaped LOCAL
stack (Caddy edge; `prod.yml` untouched). Verified through the edge:
the Speech Studio page serves (leak-sweep clean), and the page's exact
fetch shape returned 200 `audio/wav` — 15.28 s @ 24 kHz mono for a
sentence that exercises EVERY fix at once. Semantic playback proof
(our own STT judging the audio):

> **"Hello, Sumit. Welcome to IntelliAI. Your invoice of $4.99 is due
> on 12 August, 2026. Call plus 91-98765-43210 with questions."**

Sumit spoken (was dropped), IntelliAI spoken, the slash-date audibly
normalized, the phone number spoken digit-wise. Evidence:
`evidence/m35-web-e2e.json`. The human click-through is the founder's
two-minute step: open `https://localhost/console/speech`, connect the
key on Home, Generate, press play (browser playback of WAV/24k/mono is
standard Chrome-supported audio; the machine-side path is fully
verified).

## 14. Regression results — every M35 goal met or beaten

| Metric | M33 before | M35 after | Goal |
|---|---|---|---|
| Trap-set RT-WER (25 probes, same judge) | 0.1247 | **0.0659** | ≤ 0.08 ✅ (beats the research twin's 0.0716) |
| RT-CER | 0.0940 | **0.0251** | no regression ✅ |
| "Hello, Sumit." | "Hello." | **"Hello, Sumit."** (WER 0.0) | OOV preserved ✅ |
| "IntelliAI … Kavya" | both dropped | **both spoken** (WER 0.0) | ✅ |
| Median probe wall (gateway) | 1110 ms solo | **748.5 ms** (median RTF 0.168) | chunk-merge working ✅ |
| c=1 p50, pinned 120-char bench | 2972 ms | **1592 ms** | ~2× from merging ✅ |
| Ladder c=1/2/4/8 | 0.275→0.557 rps | 0.360 / 0.455 / 0.584 / **0.590 rps**, zero refusals | no regression ✅ |
| PRD TTFB (<1 s, unstreamed) | FAIL 2406 ms | FAIL **2277 ms** | expected — streaming (M8 lever) is the only general fix; `first_chunk` telemetry now measures what it would buy |
| Consistency (5×) | 5 hashes, dur stdev 0.0 | 5 hashes, dur stdev 0.0, wall stdev 20 ms | documented stochastic-sampling behavior (feature-level regression checks, never byte-equality) |

Normalization rows read "wrong" in WER exactly where they read RIGHT in
audio: the judge hears "12 August 2026" against the written reference
"12/08/2026" — the transcripts, not the score, carry those rows'
verdicts (all correct; battery 23/23 incl. refusal/auth paths).

## 15. ONNX evaluation (Phase 7) — verdict: KEEP TORCH

Community `onnx-community/Kokoro-82M-v1.0-ONNX` q8f16 via the
kokoro-onnx wrapper (MIT), same texts, same judge, pinned revision +
voices-file sha: median **RTF 1.078** (torch path: 0.168-0.29 — the
wrapper as-configured is slower than playback), RT-WER **0.0956**
(torch hardened: 0.0659; the wrapper's own G2P frontend differs), peak
RSS **1.23 GiB** (real win vs 2.4 GiB) and 1.45 s load (vs 5.1 s).
Loses the two axes that matter, wins two that don't (yet). Revisit only
as a first-party export with tuned ORT threading — PROPOSED, not
scheduled; no production switch.

## 16-18. Security · tests · CI

- Security posture (Phase 21): argv-constant stdin-only subprocess
  (hostile text is data — injection strings test-pinned), absolute
  pinned binary + version pin, 2 s timeout, fail-open; no request-time
  downloads; artifact hashes re-verified every boot; engine vocabulary
  banned from every console surface (sweep extended) and from public
  errors; the customer's text still never appears in logs (counts only).
- Tests: runtime **101** (was 65: +normalization 12, +OOV/splice/
  boundary 15, +naming/posture updates) · api **647** (+billing 4,
  +console 2, +ops-wiring 4) · evaluation 677 · contract 46 — all
  green; ruff + format clean; **mypy strict clean (334 files)**.
- Instruments committed under
  `research/experiments/35-kokoro-hardening/harness/` (battery, ONNX
  eval); WAVs stay out of git per the standing law.

## 19. Production status

Unchanged, deliberately: `prod.yml` ships no TTS service; nothing was
deployed; no production catalog/billing activation. What production
WILL get, when the founder launches TTS, is already rehearsal-shaped:
image + smoke + seed law + the M31 checklist pattern.

## 20. Next milestone (PROPOSED)

**M36 — Hindi TTS serving path** (M32 §25, now unblocked by this
milestone's espeak boundary: the same component un-gates Hindi voices)
— or, if launch comes first, **TTS production enable-promotion**
(Hostinger-gated): prod overlay flag, seed kokoro into `seed-models`,
gateway health roster entry, card badge flip on the founder's launch
call. Streaming (the PRD TTFB lever) remains the M8-shaped decision,
now priced by real `first_chunk` telemetry.
