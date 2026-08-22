# Hindi TTS Research & Model Selection (Milestone 38)

| | |
|---|---|
| **Status** | RESEARCH COMPLETE — recommendation at §21/§24; nothing ships in this milestone (no runtime, API, catalog, or production change) |
| **Date** | 2026-08-22 |
| **Scope** | The Hindi TTS workstream: what exists today, the fixed M38 Hindi benchmark, the 2026-08-22 candidate landscape re-verified at source, licenses, datasets, head-to-head measurements, one-architecture recommendation, and the exact M39 definition |
| **Evidence** | `research/experiments/38-hindi-tts-selection/` (probe set, harness, evidence JSONs) · audition pack `docs/research/audition/2026-08-22-hi-tts/` · web verifications dated 2026-08-22 |
| **Labels** | VERIFIED FROM REPO · MEASURED (this milestone, this machine) · WEB-RESEARCHED (at source, 2026-08-22) · ESTIMATED · UNKNOWN · PROPOSED |

The one-paragraph story: English TTS closed its arc at M37; Hindi is
next. M32 already measured a promising Kokoro Hindi research path
(clean CER ≈ 0.035). M38 re-measured it on a bigger, harder fixed
benchmark — four voices, not one — re-swept the 2026 landscape at
source, benchmarked the OpenRAIL runner-up and the one genuinely new
permissive Hindi specialist, and found two decision-grade new facts:
the upstream Kokoro path **silently truncates long Hindi** (~510
phonemes), and Supertonic **hard-crashes on Devanagari numerals and
long Hindi text**. The recommendation is unchanged in direction and
now much better armed: **Option A — extend the incumbent Kokoro-82M
to Hindi through the subprocess-espeak G2P the M35 hardening already
shipped for English OOV**, with a Hindi normalization layer doing the
work quality actually depends on.

---

## 1. Current Hindi TTS state — VERIFIED FROM REPO + MEASURED

**What exists**: a complete, hardened English TTS product (M35-M37):
`POST /v1/audio/speech` (+ `stream:true`), `GET /v1/audio/voices`,
Speech Studio at `/console/speech`, characters-only billing, staging
tier only (production ships no TTS).

**What Hindi gets today** (all verified/measured 2026-08-22):

- **Registry**: `intelliai-tts × hi = UNAVAILABLE`
  (`apps/api/src/intelliai_api/registry/catalog.py:258-262`) — the
  honest catalog refusal, unchanged since M3. Same for `ar`.
- **Voices**: all four public voices (`english-female`, `english-male`
  + legacy aliases) declare `languages: ["en"]` (voices endpoint,
  verified live). No Hindi voice exists anywhere in the product.
- **But text is not language-gated** — the voice is the routing key
  and there is no language field, so Devanagari input IS accepted and
  synthesized by the English pipeline. MEASURED (Phase 1, live
  local-prod stack, `evidence/production-en-path-*`): every Devanagari
  word is OOV to the EN dictionary G2P, falls to the M35 espeak
  fallback pinned to `en-us`, and comes out English-accented and
  partly garbled — "नमस्ते, आपका नाम क्या है?" round-trips as
  "नमस्ते आप कानून किया है।"; "इसकी कीमत ₹12,500 है।" becomes
  English number words ("...ट्वेल्व थाउज़ेंड फ़ाइव हंड्रेड रुपये...")
  because the EN normalization rule fires inside Hindi text.
  Full-set numbers in §8. **This is a NEW behavior vs M32** (then:
  OOV words silently dropped; now: spoken with the wrong-language
  G2P) — the M35 fallback changed the failure mode from silence to
  accent collapse. Neither is shippable Hindi.
- **Why unavailable**: the M3 license firewall — Kokoro's Hindi G2P
  is espeak-ng (GPL), banned in-process; the compliant subprocess
  posture was only blessed and shipped (for EN OOV) at M35. Hindi
  voice packs were never added to the artifact; the registry refusal
  is the deliberate honest state, not a bug.

## 2. The Kokoro Hindi path — VERIFIED FROM REPO + WEB-RESEARCHED

- **Voice packs** (upstream `hexgrad/Kokoro-82M` VOICES.md, verified
  2026-08-22): `hf_alpha`, `hf_beta` (F), `hm_omega`, `hm_psi` (M) —
  all upstream grade **C**, minutes-scale training data. ~0.5 MB each,
  same artifact repo as the four EN files we already hash-pin.
- **G2P**: upstream `kokoro/pipeline.py` routes `lang_code='h'` to
  `misaki.espeak.EspeakG2P(language='hi')` — espeak-ng end to end; no
  espeak-free Hindi G2P exists in misaki (verified at source).
- **Upstream state**: dormant — last model-repo commit 2025-04-10, no
  v1.1, no new Hindi voices, no training pipeline (unchanged).
- **The compliant shape already exists in OUR repo**: M35's
  `EspeakSubprocessFallback` (constant argv, stdin transport, version
  pin, 2 s timeout, fail-open) is the same binary at the same exec
  boundary — MEASURED this milestone: `espeak-ng -q --ipa -v hi` over
  stdin phonemizes Hindi exactly like the in-process chain, including
  the `(en)…(hi)` switch-markers on Latin tokens that M32's parity
  probe catalogued. Hindi needs: `-v hi`, sentence-level calls (G2P,
  not per-word fallback), marker stripping, and misaki's Apache
  `EspeakG2P` transform table instead of the EN `E2M` cascade —
  engineering, not research.
- **espeak-ng version facts**: research chain and system CLI both
  1.51 (measured); latest upstream release 1.52.0 (2024-12-12), no
  Hindi changes since 1.49.2 (WEB-RESEARCHED). The M35 pin law
  (version-prefix refusal) carries over.

## 3. Existing measurements (M32, 2026-08-20) — the baseline M38 re-tests

hf_alpha via upstream KPipeline, 24 hi probes, E3 judge: WER 0.1615 /
CER 0.1190 all-24; **0.0834 / 0.0347 clean slice**; RTF 0.2875; TTFA
(first chunk) 0.68-1.26 s; RSS 2.17 GiB; "zero failures incl. the
long paragraph". M38's re-run reproduces the comparable slice almost
exactly (§8) — and **overturns the long-text claim**: the M32 set's
longest probe (545 chars) was itself already silently truncated; M32
never compared audio duration against text length (§17).

## 4. The M38 Hindi benchmark — research instrument, fixed

`research/experiments/38-hindi-tts-selection/probe-texts-hi-v1.json` —
**61 cases**: the M32 hi/mixed probes VERBATIM (24 of them judged
apples-to-apples against M32) + M38 additions for every spec
category M32 lacked: exclamation, **Devanagari numerals (४५, ९)**,
percent, plain + grouped phone numbers, 10:30 AM time, slash-date
inside Hindi, place names, org/product names, abbreviations (डॉ.,
OTP, UPI), technical, and a **Hindi long-text ladder 118 / 298 / 683 /
1189 / 1897 chars** (all under the 2000-char law). Same texts for
every candidate; same judge (E3 through the real gateway, frozen
normalization profiles, `intelliai_evaluation.accuracy`); solo-timing
law enforced (every timing run serialized; one crashed first attempt
at the concurrency probe was discarded and re-run).

## 5. Candidate landscape — WEB-RESEARCHED at source, 2026-08-22

Full sweep in the task record; the decision-relevant rows:

| Candidate | Params | Hindi | Weights license | CPU | Verdict for M38 |
|---|---|---|---|---|---|
| **Kokoro-82M** (incumbent) | 82M | 4 voices, grade C | Apache-2.0 | proven | **Benchmarked (4 voices)** |
| **Supertonic 3** | 99M | yes (31 langs) | **OpenRAIL-M** | proven ONNX | **Benchmarked** — runner-up with new hard failures |
| **SPRINGLab F5-Hindi-24KHz** | 151M | dedicated | **CC-BY-4.0, card: trained from scratch** (no NC-F5 init) | flow-matching: measured §10 | **Benchmarked** — the one new permissive specialist |
| Chatterbox Multilingual(-hi) | 0.5B | yes | MIT | undocumented; GPU tier | P2 ownership lineage, unchanged; nano/turbo are EN-only |
| IndicParler-TTS (AI4Bharat) | 0.9B | yes | Apache-2.0 | marginal; needs per-request style *description* prompt | Not benchmarked: serving misfit + size |
| Magpie-TTS Multilingual v2607 | 364M | yes (since v2602) | NVIDIA OML | M33 MEASURED RTF 1.30 — fails CPU bar | REVIEW class, GPU tier |
| Qwen3-TTS 0.6B/1.7B | 0.9-2B | **still no Hindi** (card re-verified) | Apache-2.0 | poor (M34) | Out — no Hindi |
| Veena (Maya Research) | 3.78B | yes + Hinglish | Apache tag, Llama lineage unresolved | GPU-only | REVIEW + wrong size class |
| Orpheus 3b-hi / svara-TTS v1 | 3B | yes | Apache tag, gated / Llama-3.2 base flows through | GPU | REVIEW + wrong size class |
| MahaTTS (Dubverse) | 527M | yes | Apache-2.0 | poor; stale since 2024 | Not pursued |
| Piper hi_IN (pratham/priyamvada/rohan) | ~20M | yes | voices' TRAINING DATA: CC-BY-**NC**-SA / IITM custom | excellent | **BLOCKED (data provenance)** — also closes the sherpa-onnx route |
| MMS-TTS-hin | 36M | yes | CC-BY-NC (re-verified) | — | BLOCKED, unchanged |
| IndicF5 | 0.4B | yes | card MIT; **GitHub still has NO LICENSE file; from-NC-F5 init still unclarified** | hostile | BLOCKED (provenance), unchanged — and its finetunes (orato, Hinglish recipes) inherit the block |
| MeloTTS | ~52M | **no Hindi** (confirmed) | MIT | good | Out |
| Sarvam bulbul v3/V4 | — | yes | **API-only, no open weights** (HF org checked) | — | Not a self-host candidate |

New since the M32 sweep: Magpie gained Hindi (v2602, 2026-03) but
stays NOML+GPU; Chatterbox nano/turbo arrived but EN-only; sherpa-onnx
packages Supertonic-3 int8 (inherits OpenRAIL); **SPRINGLab
F5-Hindi-24KHz is the only new CLEAR Hindi entrant** — and it doubles
as evidence for §22 (a from-scratch F5-small on CC-BY Indic data is
exactly an E-TTS-1-shaped artifact someone else already built).

## 6. License audit — CLEAR / REVIEW REQUIRED / BLOCKED

| Component | License (source, 2026-08-22) | Class |
|---|---|---|
| Kokoro-82M weights + kokoro/misaki pips | Apache-2.0 | **CLEAR** |
| Hindi voice packs (hf_*/hm_*, same repo) | Apache-2.0 (repo license covers voices/) | **CLEAR** |
| espeak-ng binary for `hi` G2P | GPL-3.0 **binary at exec boundary** — the identical component M35 shipped for EN OOV (posture recorded CLOSED at M3 §8 + M35) | **CLEAR under the recorded posture** (no new policy surface: same binary, same argv discipline, one more `-v` value) |
| Supertonic 3 weights | OpenRAIL-M (re-verified; code MIT) | **REVIEW REQUIRED** — founder stance still open (M32 Q3) |
| SPRINGLab F5-Hindi weights | CC-BY-4.0; card states trained from scratch on IndicTTS-Hindi + IndicVoices-R | **CLEAR** (attribution obligation noted; F5-TTS *code* MIT) |
| Chatterbox multilingual/-hi | MIT (re-verified per-card) | CLEAR (GPU tier; Perth watermark product question stands) |
| IndicParler-TTS | Apache-2.0 (card) | CLEAR (not selected on serving fit) |
| Magpie + NanoCodec | NVIDIA Open Model License | REVIEW REQUIRED |
| Veena / Orpheus-hi / svara | Apache tags over Llama-lineage bases; Orpheus gated | REVIEW REQUIRED (lineage) |
| Piper hi voices / MMS-hin / IndicF5 + derivatives | NC data / NC / no-license+provenance | **BLOCKED** |

## 7. Hindi datasets — WEB-RESEARCHED at source, 2026-08-22 (research only; nothing downloaded)

| Dataset | HI hours | Speakers | Studio | Rate | License | Fine-tune | Eval |
|---|---|---|---|---|---|---|---|
| **SYSPIN** (IISc) | ~80 (~40/speaker) | 1M+1F | yes | 48 kHz/24-bit | **CC-BY-4.0** (terms PDF verified) | **anchor** | held-out |
| **Rasa** (AI4Bharat) | **50.83** (F 27.05 / M 23.78) | 1M+1F | yes | 48 kHz | CC-BY-4.0 | **expressive complement** | good |
| **IndicVoices-R** | 74.6 (70.3 extempore) | 399 | enhanced-ASR | 44.1/48 | CC-BY-4.0 | multi-speaker robustness only | good |
| Common Voice hi **v26.0** | **1,065 total / 520 validated** | 8,174 | crowd | MP3 | CC0 | no (flagship voice) | **excellent** (real-device) |
| FLEURS hi_in | ~12 | few | read | 16 kHz | CC-BY-4.0 | no | standard eval |
| IndicTTS (IIT-M) | ~10.3 (HF mirror) | 1M+1F | yes | 48 kHz | custom sign-up; terms PDF unreachable — **UNVERIFIED** | blocked until read | blocked |
| Vaani (ARTPARK) | large, HI split UNVERIFIED | 156K total | spontaneous | — | CC-BY-4.0 | no | dialect robustness |
| OpenSLR 103/118, Shrutilipi, Kathbath, Dhwani | — | — | — | 8 kHz/varied | restricted / NC / broadcast-rights / unverified | no | no (for us) |
| RESPIN-S1.0 (NeurIPS'25) | share of 10K+ h | crowd | no | — | CC-BY-4.0 (AIKosh) | no | **dialect eval, new** |

Common Voice Hindi growing to 520 validated hours (CC0) is the
notable 2026 change; SYSPIN + Rasa remain the M32 §22 fine-tuning
anchors, unchanged.

## 8. Quality — RT-WER/RT-CER, E3 judge, MEASURED

All five candidates synthesized the SAME 61 texts on the SAME machine,
judged by the SAME promoted E3 route with frozen normalization.
"Clean slice" = hi-language rows minus verbalization-prone categories
(numbers/currency/dates/percent/phone/time/Devanagari-numerals/
abbreviations) and minus ladder/long rows (those measure truncation,
§17). Context: E3's CER on real Hindi speech is 0.11612.

| Path | hi all (48) | hi M32-comparable (24) | **hi clean (28)** | mixed CER (10) |
|---|---|---|---|---|
| Kokoro-hi **hf_alpha** (F) | 0.3043 / 0.2668 | 0.1634 / 0.1191 *(M32: 0.1615 / 0.1190 — reproduced)* | **0.0593 / 0.0193** | 0.6062 |
| Kokoro-hi hf_beta (F) | 0.3124 / 0.2685 | 0.1764 / 0.1175 | 0.0710 / 0.0222 | 0.6098 |
| Kokoro-hi hm_omega (M) | 0.3106 / 0.2738 | 0.1705 / 0.1237 | 0.0653 / 0.0255 | 0.6211 |
| Kokoro-hi **hm_psi** (M) | 0.2887 / 0.2685 | 0.1396 / 0.1162 | **0.0450 / 0.0178 — best of all five** | 0.6211 |
| Supertonic 3 hi (F1) | 0.2268 / 0.2072 (45 rows — 3 CRASHED) | 0.1433 / 0.1126 | 0.0611 / 0.0234 | 0.5788 |
| F5-Hindi (CPU) | 0.2262 / 0.1281 | 0.1694 / 0.0850 | 0.1690 / 0.0596 | 0.5824 |
| **Production EN path today** (Phase 1 baseline) | 0.7123 / 0.5208 | 0.5935 / 0.4143 | **0.6054 / 0.3380** | 0.7441 |

Readings:

- **All four Kokoro Hindi voices and Supertonic sit in one clean band
  (WER 0.045-0.071 / CER 0.018-0.026)** — better than E3's error on
  real speech; intelligibility is a tie, again. **hm_psi**, never
  measured before, is the best-scoring voice of the five.
- The "hi all" numbers are dominated by verbalization conflation, not
  acoustics: "12345" → "बारह हज़ार तीन सौ पैंतालिस" and "12 अगस्त
  2026" → "बारह अगस्त दो हज़ार छब्बीस" are CORRECT speech punished by
  edit distance against written forms. Per-row transcripts in the
  evidence carry the honest picture; the two real defect families are
  §15's normalization gaps and §17's truncation.
- **F5-Hindi decomposes differently**: its LONG text is the best
  measured (ladder RT-WER 0.0424 — internal chunking, zero truncation)
  but short clean sentences land at 0.169 WER (~3× the incumbent) and
  — decisive for us — **Latin tokens and digits are DROPPED outright**
  (the 355-byte vocab is Devanagari-only): "IntelliAI का नया version
  आज release हुआ है" → judge heard "नया आज वह आ हुआ है"; "₹12,500"
  and "४५" vanish. A Hinglish call-center product cannot ship that.
- Error-category breakdown (per-engine `*-summary-m38.json`):
  names/places/general/questions/prosody rows round-trip at ≈0 error
  on every Kokoro voice; the loss lives in numbers/currency/dates/
  phone (normalization), mixed rows (Latin-vs-Devanagari script gap,
  not unintelligibility), and the ladder (truncation).

## 9-13. Performance — MEASURED (WSL research venvs, solo runs)

| Path | median RTF | p95 | TTFA (first chunk) | peak RSS | load |
|---|---|---|---|---|---|
| Kokoro-hi hf_alpha (torch CPU) | **0.169** | 0.195 | 0.53-0.72 s short; = wall on unchunked long (§17) | 2.28 GiB | 7.4 s |
| Kokoro-hi other 3 voices | 0.181-0.185 | 0.21-0.22 | same mechanism | 2.2-2.4 GiB | 6.6-7.2 s |
| Supertonic 3 hi (ONNX CPU) | 0.329 | 0.597 | none (single-shot) | **1.18 GiB** | 1.2 s |
| F5-Hindi (torch CPU, NFE 32) | **6.34** (short ~5.5; long ~3.2 via internal chunking) | 15.56 | none (whole-utterance flow matching) | **4.10 GiB** | 9.6 s |
| Production gateway today (EN path, for reference) | 0.188 | — | median wall 699 ms | container 2.4 GiB | — |

Machine note: this pass ran on a quieter machine than M32 (M32
measured alpha at RTF 0.288; M35 measured torch EN at 0.168-0.29) —
cross-engine comparisons within this table are same-day, same-machine.

**Concurrency (Phase 12)** — `m38-kokoro-hi-concurrency.json`,
in-process thread ladder over ONE loaded model, 298-char text,
research-only (no gateway/admission; NOT production capacity):

| c | wall | per-req p50 | throughput (audio-s/wall-s) |
|---|---|---|---|
| 1 | 4.9 s | 4.9 s | 4.8 |
| 2 | 8.5 s | 8.5 s | 5.6 |
| 4 | 14.3 s | 14.3 s | 6.6 |
| 8 | 24.2 s | 23.8 s | 7.8 |

Same CPU-bound shape as the English ladder: aggregate throughput
rises, per-request latency grows ~linearly; the production pool
(2 exec + 8 queue) and replicas remain the capacity levers.
Supertonic and F5 were NOT laddered (single-shot APIs, and neither
survives the earlier screens) — recorded, not hidden. **Found
while building it**: the in-process GPL espeak chain is NOT
thread-safe (concurrent phonemize corrupts espeak's buffer —
UnicodeDecodeError; first run crashed and is discarded). The probe
serializes G2P behind a lock; the production shape — one subprocess
per call — is structurally immune.

**GPU (Phase 11)**: no candidate that passed license + CPU screening
needs the GPU tier; Magpie/Chatterbox/Orpheus-class GPU runs remain
deliberately unrun (M32/M33 precedent). F5-Hindi GPU: deliberately
unrun — the CPU verdict (RTF 6.3) plus the interface class (per-request
reference cloning, no streaming, second engine) already disqualify the
serving fit at every tier; a GPU number would not move the decision.
RTX 5070 8 GB fits every candidate ≤0.5B for inference (ESTIMATED).

## 14-15. Code-switching + numbers/normalization — MEASURED

Hinglish (Devanagari + English tokens) through Kokoro-hi is the
strongest measured behavior of any candidate:

- "IntelliAI का नया version आज release हुआ है।" → E3 heard "इंटेली एआई
  का नया वर्शन आज रिलीज हुआ है।" — perfect. office/call/please/
  meeting/report/laptop/policy number: all correct loanword renderings
  across the M38 code-switch set.
- Degradations, named: "Python" → "पाइसन" (M32-known), "unauthorized"
  → "अनऑर्डराइज्ड", "QwikCart" → "क्यूएक कार्ड", **"OTP" → "अयोध्या
  पी"** (letter-sequence reading failed). Supertonic says OTP/UPI/
  QwikCart better but breaks all digit verbalization (below).
- **Romanized Hinglish stays unreliable** ("aaoge" → "आरेंज") — the
  roman→Devanagari transliteration requirement (M32) stands.

Hindi normalization needs (each backed by a measured row):

| Written form | Kokoro-hi today | Supertonic today | Needed rule (PROPOSED, M39) |
|---|---|---|---|
| ₹12,500 | comma splits: "बारह पाँच सौ" | garbage | ₹ + de-comma → "बारह हज़ार पाँच सौ रुपये" (Hindi words, not the EN rule's English words) |
| 9876543210 (phone) | read as one 10-digit number ("नौ अरब...") | garbage | digit-by-digit in Hindi ("नौ आठ सात...") |
| 12/08/2026 | "स्लाश" spoken | garbage | Hindi date expansion ("बारह अगस्त दो हज़ार छब्बीस") |
| **४५ (Devanagari digits)** | **misread as "पंद्रह सौ"** | **hard ValueError crash** | map ०-९ → ASCII digits (or words) before G2P |
| 12345 / 12 अगस्त 2026 / 25% | correctly expanded by espeak-hi | 12345 → English digit names; date garbage | keep (already correct) — only the judge punishes it |
| 10:30 AM | partial | partial | time rule, Hindi words |
| Aap kal office aaoge? | mangled | — | roman→Devanagari transliteration (deferred decision, M32 Q-standing) |

The English normalization ARCHITECTURE (fixed-order rules at the
pipeline seam, speech-only, original text = billing fact, rule_hits
logged) transfers as-is; the English RULES do not — the M38 Phase-1
baseline shows the EN rupee rule actively injecting English words
into Hindi sentences. Hindi TN v1 is its own small rule-pack.

## 16. Punctuation / prosody — MEASURED (signal level)

`kokoro-hi-prosody-m38.json`, hf_alpha pairs: danda vs bare —
deltas ≈ 0 (duration 0.0 s, F0 slope −0.07); "?" vs bare — duration
+0.025 s, tail slope −2.54 vs −1.42 Hz/frame (**flatter WITH the
mark; no interrogative rise — reproduces M32**); comma pair — pause
rendering present. Same conclusion, now twice-measured: keep feeding
the M30 punctuation (pauses respond), do not promise question
intonation, naturalness stays a human question. Danda IS honored by
espeak as a sentence break acoustically; what danda does NOT do is
reach our runtime's chunker (§17).

## 17. Long text — MEASURED, the milestone's second big find

Upstream KPipeline (`lang h`) ladder, hf_alpha:

| chars | audio out | verdict |
|---|---|---|
| 118 | 11.1 s | complete |
| 298 | 23.5 s | complete |
| 683 | **23.9 s** | **TRUNCATED** |
| 1189 | **23.9 s** | **TRUNCATED** (RT-WER 0.72) |
| 1897 | **23.9 s** | **TRUNCATED** (RT-WER 0.83) |

Everything beyond ~300-350 chars saturates at exactly the same ~23.9 s
— the ~510-phoneme model cap swallowing a danda-only paragraph that
upstream never splits (it splits on newlines; our runtime splits on
`[.!?;:]` — danda `।` is in neither). The truncation is SILENT: no
error, wall time flat (§9 table shows ladder walls ~4.5 s from 683 to
1897 chars — it synthesizes the same prefix). This retroactively
corrects M32's "zero failures incl. the long paragraph": its 545-char
probe was already truncated, unnoticed because nobody compared audio
seconds against text length. **M39's danda-aware chunking is a
correctness requirement, not a latency nicety.** Our production
engine's `_chunks`/`_wrap_long_sentence_to` machinery already handles
the flush-and-wrap logic — it needs `।` (and `॥`) in
`_SENTENCE_SPLIT`, one line plus tests. Supertonic fails the same
ladder harder: ONNX broadcast crash at 1189+ chars (its internal
chunking gives up instead of truncating).

## 18. Streaming / TTFA

Kokoro-hi yields per-chunk through the same engine seam the M36
streaming rides: measured first-chunk 0.53-0.72 s on short/normal
text (hf_alpha rows). Once danda chunking exists, Hindi inherits the
ENTIRE M36 stack unchanged — `stream:true`, small-first-chunk plan,
priming, billing law, browser playback, Stop, M37 PlaybackSession.
Supertonic: single-shot API, no incremental audio (unchanged);
F5: whole-utterance flow matching, no streaming. Only the incumbent
architecture streams today.

## 19. Voice inventory — MEASURED

Four Hindi voices exist, all grade C upstream: hf_alpha (F, M32's
pick, clean 0.0593), hf_beta (F, 0.0710), hm_omega (M, 0.0653),
**hm_psi (M, 0.0450 — best measured)**. Two female + two male =
enough for a `hindi-female` + `hindi-male` launch pair mirroring the
English naming law (internal pack ids never leak — same M35
discipline). WHICH female and WHICH male ships is the founder's
listening call: the audition pack
(`docs/research/audition/2026-08-22-hi-tts/`, 8 texts × 5 candidates,
40 WAVs at the session scratchpad `m38-audition/`) is assembled and
**UNSCORED**. Supertonic exposes shared style presets, not Hindi
voices; F5-Hindi has no voice inventory at all (it clones whatever
reference you hand it — a consent-gated interface class).

## 20. Decision matrix

| Model | License | Params | hi clean RT-WER/CER | TTFA | RTF (CPU) | RAM | Long text | Devanagari digits | Code-switch | Streaming | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Kokoro-82M + subprocess espeak-hi** | Apache + GPL binary at exec boundary (recorded posture) | 82M | 0.045-0.071 (4 voices) | 0.5-0.7 s chunk-level; M36 stack inherits | **0.169-0.185** | 2.2-2.4 GiB (shared with EN — **+0 new RAM**) | needs danda split (1-line + tests) — engine chunker already wraps | misread → TN rule fixes | **best measured** | **yes (M36, inherited)** | **RECOMMENDED** |
| Supertonic 3 hi | **OpenRAIL-M** | 99M | 0.0611 | none | 0.329 | 1.18 GiB (second engine, additive) | **crashes >1189c** | **crashes** | good brands, **broken digits** | no | Runner-up on paper, now with two hard failure classes + license gate |
| F5-Hindi (SPRINGLab) | CC-BY-4.0 | 151M | 0.1690 / 0.0596 (~3× incumbent) | none | **6.34** | 4.10 GiB | **best measured** (no truncation, ladder WER 0.042) | **dropped silently** (Devanagari-only vocab) | **drops Latin/digit tokens** | no | Fails serving screens (CPU, code-switch, interface); stays as the from-scratch CC-BY recipe proof |
| Chatterbox-Multilingual-hi | MIT | 0.5B | NOT MEASURED | — | GPU tier | — | — | — | claimed | no | P2 ownership lineage (unchanged) |
| IndicParler-TTS | Apache-2.0 | 0.9B | NOT MEASURED | — | marginal (CLAIMED) | — | — | — | — | no | serving misfit (style-prompt per request) |
| Magpie-TTS ML | NVIDIA OML | 364M | NOT MEASURED (hi) | — | 1.30 (M33, EN) | 1.4 GiB | 20 s windows | — | — | no | fails CPU bar + REVIEW |
| Production EN path today | — | — | 0.6054 / 0.3380 | — | — | — | — | — | — | — | the baseline M39 must retire |

MEASURED unless marked CLAIMED/NOT MEASURED; naturalness column
deliberately absent — UNSCORED until the founder listens.

## 21. Model strategy — Option A, re-confirmed with more evidence

**A. Kokoro English + Kokoro Hindi: one engine, one process, two
languages.** What M38 adds over M32's same conclusion:

1. **Zero new RAM, zero new engine**: Hindi = 2-4 voice-pack files
   (~0.5 MB each) + one G2P subprocess component we already ship.
   Every alternative adds a second engine and its own failure classes.
2. **The hardening arc transfers whole**: billing law, TN seam,
   streaming, playback, artifact pinning, smoke, leak-guards (§23).
3. **Quality ties, robustness doesn't**: the four Kokoro voices and
   Supertonic tie on clean intelligibility, but only the incumbent
   path survived the full M38 battery (Supertonic: 2 crash classes;
   F5: clean WER ~3× worse and drops English tokens + digits
   outright).
4. **License posture is already decided**: the espeak exec-boundary
   call was made and recorded at M35 — Hindi adds a `-v hi` argument,
   not a new policy question. OpenRAIL (Supertonic) would be a new
   founder call for a worse-measured engine.

B (Hindi specialist beside Kokoro): the only CLEAR specialist is
F5-Hindi — measured out on four independent axes (CPU RTF 6.34; clean
WER 0.169; Latin/digit dropouts from a Devanagari-only vocab; a
per-request reference-cloning interface with no streaming) — it would
also be a SECOND 4-GiB engine. C (one multilingual replacing both):
no candidate beats the incumbent on EN (M33/M34) AND HI (M38).
D (fine-tuned own model): that is E-TTS-1 (§22) — sequenced after
serving, exactly as M32 planned.

## 22. Future fine-tuning — E-TTS-1 unchanged, one new datapoint

The M32 §22 definition stands (VITS-class ~36-45M, SYSPIN Hindi
female, Devanagari-grapheme vs espeak-phoneme ablation, 8 GB 5070).
New evidence this sweep: SPRINGLab already proved the adjacent recipe
— an F5-small trained FROM SCRATCH on IndicTTS+IndicVoices-R under
CC-BY — so "own a permissive Hindi voice trained on open data" is a
demonstrated path, not a bet. Their model's serving shape (cloning
interface, flow matching, no streaming) is exactly what E-TTS-1's
VITS choice avoids. Datasets re-verified (§7): SYSPIN anchor + Rasa
expressive complement, both CC-BY-4.0.

## 23. Reuse from M35-M37 — the Hindi milestone inherits almost everything

| Reused AS-IS | Hindi-specific work |
|---|---|
| Billing (characters-only, streamed law F1) | espeak-hi G2P component (subprocess, `-v hi`, marker stripping, EspeakG2P transform table, version pin) |
| TN seam + laws (speech-only, original text = billing fact) | Hindi TN v1 rules (₹/dates/phone/percent in HINDI words; ०-९ digit mapping; time) |
| M36 streaming (run_stream, priming, first-chunk plan) | danda `।`/`॥` in `_SENTENCE_SPLIT` (correctness — §17) |
| M37 PlaybackSession browser stack | 2 public Hindi voices + naming (hindi-female/hindi-male), packs hash-pinned |
| Artifact governance (SHA pinning, /info, stale-image smoke) | registry `hi` route flip (staging only) + voices endpoint languages |
| WorkerPool admission + pool laws | Hindi regression battery (this probe set) + judge wiring |
| tts-smoke.sh (extend §4 voices + version floor) | founder listening gate on voice pick |

## 24. Final recommendation

**A. KOKORO HINDI** — extend the incumbent artifact to Hindi via the
subprocess espeak-ng `hi` G2P, ship `hindi-female` + `hindi-male`
voices (pack choice founder-gated on the audition pack), with Hindi
normalization v1 and danda-aware chunking as first-class parts of the
milestone, staging tier only. Supertonic 3 remains the named runner-up
strictly behind the founder's OpenRAIL stance and now carries two
measured hard-failure classes; F5-Hindi enters the ledger as
Researching — measured, not a serving candidate; its standing value is
proving the from-scratch CC-BY Hindi training recipe E-TTS-1 rhymes
with.

## 25. Next milestone — M39 (defined, NOT implemented)

**M39 — Hindi TTS Local Web Implementation** (founder-gated):

- **Model/artifact**: kokoro-82m, same 4 pinned files + `hf_alpha.pt`,
  `hf_beta.pt`, `hm_omega.pt`, `hm_psi.pt` SHA-pinned from
  `hexgrad/Kokoro-82M` (revision recorded at fetch; upstream dormant).
- **G2P**: `EspeakHindiG2P` beside the M35 fallback — same binary,
  constant argv `(binary, -q, --ipa, -v, hi)`, stdin transport,
  version pin, timeout, loud startup failure; `(en)/(hi)` marker
  stripping + vendored EspeakG2P transform table; parity tests from
  the M32 table.
- **Chunking**: `।` and `॥` join `_SENTENCE_SPLIT`; ladder regression
  proves audio duration scales with text to 2000 chars (the §17 trap,
  pinned).
- **Normalization**: Hindi TN v1 rule-pack behind the existing seam
  (₹/paise, dates incl. slash-dates, phone digit groups, percent,
  ०-९ mapping, 10:30 AM), Hindi words out; original text stays the
  billing fact; roman-Hinglish transliteration explicitly deferred
  with its own decision note.
- **API/registry**: voices `hindi-female`/`hindi-male` (+ languages
  `["hi"]` on the voices endpoint), registry `hi` route
  UNAVAILABLE→AVAILABLE in dev/local-staging ONLY; production
  untouched; Android/iOS untouched.
- **Streaming/Web**: `stream:true` works day one (M36 inheritance);
  Speech Studio gains a voice picker + Hindi sample texts; M37
  playback untouched.
- **Billing**: characters-only, unchanged, cross-language pin test.
- **Tests/benchmark**: M38 probe set becomes the Hindi battery
  (targets PROPOSED: clean-slice RT-WER ≤ 0.08 through the PRODUCTION
  path; zero failures; ladder duration law; TN rule pins; leak-guard
  extension — engine vocabulary ban already covers hindi pack ids).
- **Smoke/E2E**: tts-smoke §4 gains the Hindi voices; local HTTPS
  edge + browser click-through with Hindi text, streamed.
- **Gates before it ships**: founder listening verdict on the
  audition pack (voice pick + launchability), and nothing else — the
  license posture is already recorded.

## Final answers (the 14 the spec requires)

1. **What Hindi TTS do we have today?** None as a product: registry
   refuses `hi`, all voices are EN. Devanagari text IS accepted and
   comes out English-accented/garbled through the EN pipeline
   (MEASURED §1) — clean-slice RT-WER 0.6054, roughly 10× worse than
   the 0.045-0.071 of the real Hindi paths.
2. **Why unavailable?** The M3 GPL gate on Kokoro's Hindi G2P; the
   compliant subprocess shape shipped only at M35 (for EN OOV), and
   no Hindi voices/normalization/chunking were ever added.
3. **Is Kokoro Hindi good enough?** Intelligibility: yes — clean
   RT-WER 0.045-0.071 across all 4 voices, zero failures, best
   code-switching measured. Naturalness: UNSCORED (grade-C voices;
   audition pack awaits the founder). Long text needs the danda fix
   (correctness, §17).
4. **Better alternatives?** None survive the full screen: Supertonic
   ties quality but crashes on Devanagari digits and >1189 chars and
   is OpenRAIL-gated; F5-Hindi measures clean WER 0.169 (~3× worse),
   CPU RTF 6.34, and drops English words and digits outright;
   everything else is GPU-class, license-blocked, or has no Hindi.
5. **Commercially safe?** CLEAR: Kokoro(+packs), F5-Hindi weights
   (CC-BY-4.0), Chatterbox (MIT), IndicParler (Apache). REVIEW:
   Supertonic (OpenRAIL-M), Magpie (NOML), Veena/Orpheus/svara
   (lineage). BLOCKED: IndicF5 + derivatives, Piper-hi voices,
   MMS-hin.
6. **Fastest?** Kokoro-hi: RTF 0.169-0.185 CPU, first-chunk 0.5-0.7 s
   (and the only one that streams).
7. **Smallest?** By params: Kokoro 82M. By RAM: Supertonic 1.18 GiB —
   but as a SECOND engine it ADDS RAM, while Kokoro-hi adds ~0 to the
   process already serving English.
8. **Sounds best?** UNSCORED — audition pack assembled, nobody has
   listened. Machine numbers say hm_psi leads intelligibility.
9. **Best Hinglish?** Kokoro-hi (Devanagari+English measured
   excellent; romanized Hinglish needs transliteration — every
   candidate shares that gap).
10. **Can stream?** Only the Kokoro path (M36 inheritance).
    Supertonic and F5: no incremental audio.
11. **Fits CPU-first?** Kokoro-hi and Supertonic yes; F5-Hindi no
    (RTF 6.34); all 3B-class candidates no.
12. **Kokoro or specialist?** Kokoro (Option A) — §21.
13. **Should we fine-tune?** Not yet. Serve first (M39); E-TTS-1
    stays the defined ownership experiment, strengthened by the
    SPRINGLab from-scratch proof (§22).
14. **What exactly should M39 implement?** §25, verbatim.

---

**STOP at Milestone 38** — research, benchmarks, decision matrix, and
recommendation only. No implementation, no fine-tuning, no production
or catalog change. The Hindi serving milestone (M39) and the founder
listening verdict are the two gates ahead.
