# IntelliAI STT vs Sarvam STT — Controlled Comparison (Milestone 48)

| | |
|---|---|
| **Status** | MEASURED (head-to-head n=1 real-world clip + IntelliAI-side probes) · reference transcript DRAFT pending founder listen-through · Sarvam extended battery BLOCKED pending API access |
| **Date** | 2026-08-27 |
| **Question** | Is IntelliAI's user-visible STT weakness recognition accuracy, latency, punctuation/readability, or something else? |
| **Answer (preview)** | **B — punctuation/readability is the gap.** The word-recognition delta on the same audio is tiny and inside reference-uncertainty; the punctuation delta is structural: the product ships NO English punctuation stage at all. |
| **Scope** | Research/evaluation only. Production (Qwen E3, Whisper, punctuation runtime OFF-flag, API, billing, TTS, routing) untouched — verified by the standing test suites. |
| **Evidence** | `research/experiments/48-stt-sarvam-comparison/` (audio stays OUTSIDE git per the privacy law) |

## 1-3. Background & governance

The founder ran the SAME 102.2 s real-world English voice note (WhatsApp
opus, sha `117cba69…`) through both playgrounds. Sarvam's output LOOKS
better. M48 measures why, instead of assuming.

- Benchmark item: 1 real-world clip (n=1 — stated everywhere; no
  statistical significance is claimed). IntelliAI's frozen EN/HI
  benchmarks provide context but cannot run against Sarvam without API
  access (BLOCKED — recorded, not scored).
- Rulers: WER/CER on the FROZEN `ml/evaluation` wer.py normalization
  (lowercase, punctuation stripped — so punctuation can NOT leak into
  WER). Punctuation/boundary F1 is a NEW M48 ruler v1 (per-word mark
  positions; marks `. , ? ! ।`); frozen rulers unmodified.

## 4-5. Reference transcript — DRAFT, MANUALLY-VERIFIED-PENDING

Built by triangulating both outputs word-by-word; **seven spans are
disputed between the systems and only a human listen settles them**
(the draft currently sides with Sarvam's reading on most, which is why
Sarvam's WER shows 0.0 — a known circularity, flagged, not hidden):

| # | Word pos | Draft/Sarvam reading | IntelliAI reading |
|---|---|---|---|
| 1 | ~5 | "a text which I" | "a text **to** which I" |
| 2 | ~72 | "I have **I have** placed" (doubled) | "I have placed" (single) |
| 3 | ~122 | "added a star" | "add a star" |
| 4 | ~126 | "used that filler" | "use that filler" |
| 5 | ~143 | "added the fillers" | "did the fillers" |
| 6 | ~171 | "ChatGPT" | "chat gpt" (normalization, not recognition) |
| 7 | ~192 | "proper drafts" | "proper **droughts**" |

Founder adjudication sheet = this table; final WER republishes after
the listen-through. Span 7 is near-certainly an IntelliAI recognition
error (semantics); span 6 is a normalization difference, not an error.

## 6-9. Setups (MEASURED / UNKNOWN)

- **IntelliAI**: fresh gateway run 2026-08-27, `/v1/audio/transcriptions`,
  `language=en`, contribution OFF (boss audio never stored), production
  stack. **Wall 6.71 s for 102.15 s audio (RTF 0.066).**
- **Sarvam**: founder playground capture 2026-08-26, model `saaras:v4`,
  Batch/Transcribe, English. Latency, API version, server post-processing:
  **UNKNOWN** (playground exposes none of it).

## 9-12. Scores on the boss clip (vs DRAFT reference, 214 words)

| System | WER | CER | Punctuation F1 | Boundary F1 |
|---|---|---|---|---|
| IntelliAI raw | 0.0421 (9 word-errors) | 0.0197 | **0.000** | **0.000** |
| IntelliAI + punct probe (EXPERIMENTAL, §15) | 0.0421 (unchanged — word-copy invariant held) | 0.0197 | 0.092 | 0.129 |
| Sarvam saaras:v4 | 0.000* | 0.000* | 0.794 | 0.875 |

\* Circular against the draft (see §4); true value after adjudication
will be > 0 if any disputed span goes IntelliAI's way. **Either way the
word-level delta is at most ~4 percentage points on n=1, while the
punctuation delta is 0.00 → 0.79 F1 — two different orders of
magnitude of "gap."**

## 13. Readability — UNSCORED

Rubric (segmentation / punctuation usefulness / readability / meaning,
1-5) ships with the comparison sheet in the evidence dir. No human
scores are fabricated; the founder's informal reaction ("Sarvam looks
better") is what triggered M48 and matches the punctuation numbers.

## 14. Latency — MEASURED (IntelliAI) / UNKNOWN (Sarvam)

IntelliAI: 6.71 s whole-response for 102 s audio (RTF 0.066); silence
probe answers in 0.29 s; ~1 s clips answer in ~1.05 s. Sarvam batch
latency is not exposed by its playground — **no comparison is claimed.**

## 15-17. IntelliAI-side probes (Sarvam side BLOCKED pending API key)

- **Silence 5 s** → `""` in 0.29 s — clean, no hallucination.
- **Short speech** (real slices of the boss clip): 0.5 s → "You";
  **1 s → "Thank you." (fabricated — the classic Whisper-family
  short/ambiguous-audio hallucination)**; 2 s → "Uh...". Recorded as a
  real weakness class (M23's short-speech regression class lives on).
- Long-audio ladder, Hinglish, numbers/names batteries: IntelliAI has
  standing frozen-benchmark coverage (ledger); the HEAD-TO-HEAD halves
  need Sarvam API access — BLOCKED, listed as the milestone's main
  limitation.

## 15b. The punctuation-only experiment — the decisive isolation

IntelliAI's raw transcript + the SAME pinned 47-language
punct-cap-seg model the platform already vendors (M30), run as an
EXPERIMENTAL research probe with an English label map (the SHIPPED v1
scope is Hindi-only: danda/comma/question, "." deliberately dropped;
production flag is OFF and untouched):

- Words: byte-identical (the word-copy invariant held) → WER unchanged.
- Punctuation F1: 0.000 → 0.092; boundary 0.000 → 0.129 — real marks
  appear, but placement on English is poor ("right fit? break the
  statement?"), far from Sarvam's 0.79/0.88.

**Reading:** the gap is punctuation, AND our existing Hindi-scoped v1
stage does not transfer to English as-is. Closing the gap needs an
English-competent punctuation/readability stage — a defined product
milestone, not a tweak.

## 18. Results table

| Metric | IntelliAI | Sarvam | Winner | Basis |
|---|---|---|---|---|
| WER (boss clip) | 0.042 | 0.000* | INCONCLUSIVE (n=1, draft ref, ≤4 pt delta) | boss-scores.json |
| CER | 0.020 | 0.000* | INCONCLUSIVE (same) | same |
| Punctuation F1 | 0.000 | 0.794 | **Sarvam, decisively** | same |
| Boundary F1 | 0.000 | 0.875 | **Sarvam, decisively** | same |
| Latency | 6.7 s / 102 s (RTF 0.066) | UNKNOWN | NOT COMPARABLE | manifest |
| Silence hallucination | clean | UNTESTED | — | probes |
| Short-speech | 1 s clip fabricates "Thank you." | UNTESTED | — | probes |
| Long audio / Hinglish / numbers | standing frozen coverage | BLOCKED (no API) | — | ledger |
| Raw-transcript fidelity | verbatim incl. fillers/repeats | normalizes ("ChatGPT", drops a repeat?) | depends on product goal | §4 spans 2,6 |

## 19-20. Product interpretation & recommendation

1. Word recognition worse? **Not materially provable** — ≤9 words on
   214 either direction; one clear IntelliAI miss ("droughts").
2. Punctuation worse? **Yes, categorically** — English output has NO
   punctuation stage; Sarvam restores sentences at F1 ~0.8.
3. Slower? **No evidence** — IntelliAI RTF 0.066 is excellent; Sarvam
   unknown.
4. Sarvam post-processing? Visible normalization ("ChatGPT",
   capitalization, casing) — consistent with a readability post-stage.
5. IntelliAI's advantage: verbatim fidelity, measured-clean silence
   behavior, fast whole-response, correction capture.
6. Does punctuation alone explain the visual difference? **On this
   clip, essentially yes.**
7. Largest user-visible weakness: **English readability** (plus the
   short-clip hallucination class as a secondary).

**Recommended next milestone (exactly one): M49 — English (+ Hindi
activation) punctuation & readability stage** — evaluate proper
English-capable punctuation models under the M29/M30 gate discipline
(the shipped word-copy wrapper and invariants are reusable; the
Hindi-only v1 label scope is what must grow). Not implemented in M48.

## 21-22. Classification & limitations

**B. READABILITY/PUNCTUATION IS THE MAIN GAP.**

Limitations, stated plainly: n=1 real clip; reference DRAFT until the
founder's listen-through (adjudication sheet above); Sarvam side
unmeasurable beyond the captured output without API access (key
requested); readability UNSCORED; Sarvam internals UNKNOWN.
