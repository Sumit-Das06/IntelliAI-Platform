# IntelliAI STT vs Sarvam STT — Controlled Comparison (Milestone 48)

| | |
|---|---|
| **Status** | MEASURED (IntelliAI side, full battery) · Sarvam quantitative comparison **BLOCKED — CREDENTIALS REQUIRED** (captured playground output used as QUALITATIVE evidence only; no Sarvam WER/CER/latency is claimed) · reference transcript DRAFT pending founder listen-through |
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

**IntelliAI (MEASURED, fresh API run):**

| System | WER | CER | Punctuation F1 | Boundary F1 |
|---|---|---|---|---|
| IntelliAI raw | 0.0421 (9 word-errors) | 0.0197 | **0.000** | **0.000** |
| IntelliAI + punct probe (EXPERIMENTAL, §15) | 0.0421 (unchanged — word-copy invariant held) | 0.0197 | 0.092 | 0.129 |

**Sarvam (QUALITATIVE ONLY — captured playground text, not an API
measurement; per the founder's directive no Sarvam WER/CER/latency is
claimed):** the captured transcript is fully sentence-punctuated
(periods, commas, question marks, capitalization throughout — a
text-structure count over the capture shows ~30 marks / ~16 sentence
boundaries against the draft's punctuation, versus ZERO in IntelliAI's
raw output), its words agree with IntelliAI's on ~96% of tokens, and
its visible normalization ("ChatGPT", casing) indicates a readability
post-stage. Quantitative scoring of Sarvam is **BLOCKED — CREDENTIALS
REQUIRED** and will run through `m48_harness.py` when access exists.

**What we can already PROVE from the capture alone:** on the same
audio the two systems heard nearly the same words, one output is
sentence-punctuated and one has no punctuation at all — and the
product reason is structural: IntelliAI ships NO English punctuation
stage. That conclusion does not depend on any Sarvam metric.

## 13. Readability — UNSCORED

Rubric (segmentation / punctuation usefulness / readability / meaning,
1-5) ships with the comparison sheet in the evidence dir. No human
scores are fabricated; the founder's informal reaction ("Sarvam looks
better") is what triggered M48 and matches the punctuation numbers.

## 14. Latency — MEASURED (IntelliAI) / UNKNOWN (Sarvam)

IntelliAI: 5-rep battery on the 102 s clip — walls 6.26-8.29 s,
**median 6.37 s (RTF 0.062)**, stable; long ladder scales linearly
(5 min → 26.9 s, 9.5 min → 52.3 s, RTF ~0.09); silence answers in
0.29 s; ~1 s clips in ~1.05 s. Sarvam latency: **BLOCKED —
CREDENTIALS REQUIRED** (playground exposes nothing) — no comparison
is claimed.

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
  statement?"), nowhere near the fully-punctuated structure of the
captured Sarvam text (qualitative comparison only — Sarvam scoring is
BLOCKED pending credentials).

**Reading:** the gap is punctuation, AND our existing Hindi-scoped v1
stage does not transfer to English as-is. Closing the gap needs an
English-competent punctuation/readability stage — a defined product
milestone, not a tweak.

## 18. Results table

| Metric | IntelliAI (MEASURED) | Sarvam | Verdict | Basis |
|---|---|---|---|---|
| WER (boss clip) | 0.042 | **BLOCKED — CREDENTIALS REQUIRED** | word agreement between outputs ~96% (qualitative) | boss-scores.json |
| CER | 0.020 | BLOCKED | — | same |
| Punctuation presence | F1 0.000 (no marks at all) | qualitative: fully punctuated capture | **readability gap is real and structural** | captures |
| Latency | 6.7 s / 102 s (RTF 0.066), ×5 reps in battery | BLOCKED | no comparison claimed | manifest, battery |
| Long audio (30 s → 9.5 min) | 5 min WER 0.067 · 9.5 min WER 0.058 · zero truncation (PASS both) | BLOCKED | — | battery |
| Short-speech | 1 s clip fabricates "Thank you." | BLOCKED | — | probes |
| Silence | clean ("") | BLOCKED | — | probes |
| Numbers/names (synthetic round-trip) | mean RT-WER 0.108 — names/IntelliAI/FastAPI/currency/date perfect; QwikCart 0.33, OpenAI 0.29, Kubernetes 0.29, slash-date 0.29 slip | BLOCKED | — | battery |
| Hinglish (synthetic) | hi route TRANSLITERATES English tokens to Devanagari (0/8 kept in Latin; "QwikCart"→"क्यूबिक कार्ड" mangled) — script policy + brand handling recorded as product questions | BLOCKED | — | battery |
| Raw-transcript fidelity | verbatim incl. fillers/repeats | qualitative: normalizes ("ChatGPT", casing) | depends on product goal | §4 spans 2,6 |

**Blocked-until-credentials list (exact reruns, all through
`m48_harness.py` + the frozen clip manifest):** Sarvam WER/CER on the
boss clip and the long ladder, Sarvam latency, Sarvam
silence/short-speech behavior, Sarvam numbers/names and Hinglish
handling. The harness's Sarvam adapter refuses with
`BLOCKED - CREDENTIALS REQUIRED` today and takes a key + endpoint when
legitimate access exists — nothing else changes.

## 19-20. Product interpretation & recommendation

1. Word recognition worse? **Not materially provable** — ≤9 words on
   214 either direction; one clear IntelliAI miss ("droughts").
2. Punctuation worse? **Yes, categorically** — English output has NO
   punctuation stage; the captured Sarvam output is fully
   sentence-punctuated (qualitative).
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
