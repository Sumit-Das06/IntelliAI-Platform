# Milestone 39 — Kokoro Hindi TTS: Local Web Implementation

| | |
|---|---|
| **Status** | COMPLETE — Hindi serves through the full existing architecture on the local/staging tier; clean-slice gate passed both voices (0.0707 / 0.0547 ≤ 0.08); the M38 truncation defect is structurally fixed and re-measured gone; English regression clean; production untouched |
| **Date** | 2026-08-24 |
| **Decision implemented** | M38 (docs/research/2026-08-22-hindi-tts-model-selection.md): Option A — extend the incumbent Kokoro-82M to Hindi; founder voice decision hindi-female=hf_alpha, hindi-male=hm_psi (fixed by the M39 spec, not reopened) |
| **Evidence** | `research/experiments/39-hindi-tts-local-web/evidence/` · new suites across tts-runtime / api |

    HINDI TTS IMPLEMENTED: YES
    HINDI WEB E2E: YES
    ENGLISH REGRESSION: PASS
    LONG-TEXT TRUNCATION: FIXED
    STREAMING: PASS
    PRODUCTION HINDI TTS: NO
    HOSTINGER: NO

    FINAL CLASSIFICATION: A — HINDI TTS READY FOR STAGING

## 1. What shipped (LOCAL/STAGING only)

One engine, two languages — the M32/M38 thesis made real. Hindi text
now flows:

    POST /v1/audio/speech (voice = hindi-female | hindi-male)
      ↓ gateway: STAGING registry resolves the voice → hi route → kokoro-82m
      ↓ runtime: Hindi normalization v1 → danda-aware chunking
      ↓ EspeakHindiG2P (pinned espeak-ng binary, exec boundary, -v hi)
      ↓ the SAME KModel pass, per bounded phoneme piece
      ↓ the SAME M36 streaming / M35 whole-body delivery
      ↓ the SAME M37 PlaybackSession in the Speech Studio

Nothing was built twice: billing, streaming, cancellation, playback,
artifact governance, health, auth — all reused byte-identical. The
Hindi-specific surface is exactly four pieces: two voice packs, one
G2P component, one normalization pack, one splitter character class.

## 2. Artifact packaging (Phase 1)

`kokoro-82m` artifact spec **v1 → v2**: + `hf_alpha.pt`
(sha256 06906fe0…) and `hm_psi.pt` (sha256 2f0f055c…), LFS oids from
the SAME pinned upstream revision (f3ff3571…) the M38 research runs
recorded, verified at boot like every artifact file. The unapproved
research packs (hf_beta, hm_omega) are NOT packaged, NOT served.
Missing/corrupt file → the store refuses, readiness stays down. No
request-time downloads (startup fetch + re-hash, as always).

## 3. Hindi G2P (Phase 2) — `EspeakHindiG2P`

The M35 exec-boundary posture, at sentence level: constant argv
`(binary, -q, --ipa, -v, hi)`, segments via stdin one-per-line, UTF-8
pinned, 2 s timeout, version pin `1.5x` refused at composition time
(startup, not first request). The IPA→Kokoro transform is misaki
`EspeakG2P`'s table (Apache-2.0, vendored with attribution) plus one
CLI reality the library never sees: the CLI ties affricates with
U+0361 but emits diphthongs bare, so the table applies in tied AND
untied (diphthong-only) forms. `(en)/(hi)` switch flags are stripped;
danda becomes a full stop pre-G2P; chunk punctuation is preserved by
segment-splitting and reassembly in the upstream output format.

**Parity: 12/12 fixture texts byte-identical to the upstream misaki
EspeakG2P(hi) output** (fixtures captured in the research venv against
espeak-ng 1.51; the CI stub replays the recorded CLI lines —
`tests/fixtures/hi_g2p_parity.json`). G2P failure fails the REQUEST
(no Hindi dictionary exists to fall back to) — never wrong audio.

## 4. Hindi normalization v1 (Phase 3) — `normalization_hi.py`

NOT a translation of the English rules. espeak's Hindi voice already
reads bare digits as Hindi number words (M38: "12500" → "बारह हज़ार
पाँच सौ"), so the pack only rewrites the measured defects:

| Rule | In | Out |
|---|---|---|
| devanagari_digits | ४५ | 45 |
| slash_date | 12/08/2026 | 12 अगस्त 2026 |
| rupees | ₹12,500 / ₹1,499.50 | 12500 रुपये / 1499 रुपये और 50 पैसे |
| percent | 25% | 25 प्रतिशत |
| time_ampm | 10:30 AM | सुबह 10 बजकर 30 मिनट |
| phone (grouped / 10-digit) | 1800 425 9090 / 9876543210 | Hindi digit words, group-paused |

No English words are ever emitted (test-pinned). Deterministic,
idempotent, speech-only — the original text stays the billing and
provenance fact. Short numeric IDs (12345, train numbers) deliberately
keep espeak's Hindi number reading. Romanized Hinglish transliteration
is NOT implemented (Phase 4, documented limitation).

## 5. Danda-aware chunking (Phase 5) — the M38 correctness gate

`_SENTENCE_SPLIT` gains `।` and `॥` (space-separated AND jammed
against the next word); Latin `.!?;:` behavior byte-identical
(space-required, decimals never split — test-pinned). The M38 defect —
danda-only Hindi reaching the model as ONE oversized input — is
structurally gone: chunk-merging and the streaming first-chunk plan
now see Hindi sentences. Long-text proof in §9.

## 6. Registry / API / voices (Phases 8-10)

- **Staging proposal (M24 mechanism)**: `staging_registry()` composes
  the live catalog + `HINDI_TTS_ROUTE` (hi → kokoro-82m, AVAILABLE,
  license verdict covering the exec-boundary posture, M38 evidence,
  approval=PENDING sentinel) + the two `PublicVoiceRecord`s
  (languages `["hi"]`). **The LIVE catalog is untouched**: production
  keeps refusing `hindi-*` voices with `voice_not_found` BEFORE any
  plane crossing, `hi` stays UNAVAILABLE, and the settings layer still
  refuses the staging profile under `INTELLIAI_ENV=prod` — all
  test-pinned.
- **API unchanged**: same `POST /v1/audio/speech`, same fields; the
  voice is the routing key (`resolve_voice` routes a single-language
  voice through its language's route). No language parameter added.
- **Runtime voices**: `hindi-female → hf_alpha`, `hindi-male →
  hm_psi`, served ONLY when the deployment declares
  `INTELLIAI_TTS_HINDI_G2P=espeak` — the voices and their phonemizer
  arrive together or not at all (wrong-version/missing binary refuses
  startup). English voices and legacy aliases: unchanged, `["en"]`.

## 7. Billing (Phase 7) — unchanged law, Hindi-proven

Characters of the ORIGINAL text, once, nothing else: a 1000-character
Devanagari request bills exactly 1000 units (test-pinned end to end,
`event.language == "hi"` recorded); speed/voice/chunk-count never
change the bill; pre-audio failures bill nothing; the M36 streamed
delivery law applies as-is. Normalization output is never billed.

## 8. Quality (Phase 13) — MEASURED through the real gateway, E3 judge

Same frozen M38 probe set (61 cases), same judge, same frozen
normalization/metric code, run against the production-shaped stack:

| Voice | all-hi WER/CER | M32-comparable | clean slice | mixed CER | ladder |
|---|---|---|---|---|---|
| hindi-female (gateway) | 0.2817 / 0.2305 | 0.1686 / 0.1162 | **0.0707 / 0.0232** | 0.6018 | 0.0482 / 0.0195 |
| hindi-male (gateway) | 0.2666 / 0.2279 | 0.1382 / 0.1077 | **0.0547 / 0.0204** | 0.6137 | 0.0288 / 0.0133 |
| M38 research twins | 0.3043/0.2668 · 0.2887/0.2685 | 0.1634 · 0.1396 | 0.0593 · 0.0450 | 0.6062 · 0.6211 | (truncated!) |

**The PROPOSED clean-slice gate (RT-WER ≤ 0.08) PASSES on both
voices**, reproducing the M38 research band through the production
path — and the ladder slice (long text) is now the BEST slice, where
M38's research twin silently truncated it.

Normalization-sensitive rows (Phase 14): high edit-distance BY
CONSTRUCTION — the normalizer correctly expands written forms into
spoken words (phone WER 1.75 = ten digits spoken as ten Hindi words
against a 10-character written reference), so these categories are
reported separately, never averaged into the gate. The audio itself
is correct — the Web E2E round-trip (§13) shows ₹4,999 spoken as
"चार हज़ार नौ सौ निन्यानवे रुपये" and 12/09/2026 as "बारह सितंबर दो
हज़ार छब्बीस". Hinglish (Phase 15): the M38-critical probe rides
clean — E3 heard "इंटेली एआई का नया वर्शन आज रिलीज हुआ है।" (every
English token spoken, both voices); romanized Hinglish stays unsolved
(documented). The mixed-CER numbers remain script-gap-dominated
(Latin reference vs Devanagari transcript — the M32/M38 caveat).

## 9. Long text (Phase 16) — the truncation defect, gone

| chars | audio_seconds (hindi-female, gateway) | M38 upstream (truncated) |
|---|---|---|
| 118 | 11.0 s | 9.2 s |
| 298 | 23.1 s | 21.4 s |
| 683 | **55.7 s** | **23.9 s (capped)** |
| 1189 | **95.6 s** | **23.9 s (capped)** |
| 1897 | **149.6 s** | **23.9 s (capped)** |

Audio grows with text at a steady ~12.7 chars/second across the whole
ladder — the M38 cap is gone (hindi-male: 11.7/23.5/58.6/100.2/155.7 s,
same shape). Zero failures on the full 61-probe battery, both voices.
Round-trip on the ladder rows confirms the CONTENT is complete, not
just long: ladder RT-WER 0.0482 (F) / 0.0288 (M) — the closing
sentences of the 1897-char text come back from the judge.

## 10. Streaming (Phase 17) + concurrency (Phase 18) — MEASURED

Best-of-3 by TTFA, production-shaped stack, per the M36 definitions
(TTFA = first byte past the WAV preamble):

| Text | whole TTFA (F) | **stream TTFA (F)** | stream TTFA (M) | speedup (F) |
|---|---|---|---|---|
| short question (25c) | 473 ms | 482 ms | 775 ms | 1.0× |
| 118 chars | 1 870 ms | **547 ms** | 893 ms | 3.4× |
| 298 chars | 4 867 ms | **746 ms** | 1 129 ms | 6.5× |
| 683 chars | 11 658 ms | **1 099 ms** | 1 552 ms | 10.6× |
| 1189 chars | 19 716 ms | **1 067 ms** | 1 528 ms | 18.5× |
| 1897 chars | 31 559 ms | **1 056 ms** | 1 572 ms | **29.9×** |

The M36 design works unchanged for Hindi: stream TTFA plateaus at
first-chunk cost (0.5-1.6 s) regardless of length — danda-aware
chunking is what hands the streaming plan its first sentence. The
M38 reference band (0.53-0.72 s research first-chunk) holds for the
female voice; the male voice runs ~0.3-0.5 s behind it on this
machine (same engine, measured fact, not an SLA).

Concurrency (streamed, hindi-female, 298 chars, c=1/2/4/8): all
requests ok, zero errors; TTFA p50 0.68 / 3.87 / 8.74 / 18.93 s —
under saturation a queued stream's first chunk honestly waits behind
executing work, exactly the M36 English behavior (pool 2+8 unchanged,
no separate Hindi pool). MEASURED LOCAL — never production capacity
claims.

## 11. English regression (Phase 19) — PASS

The M35 live battery re-run through the SAME rebuilt stack:
**23/23 PASS** — every trap the M35 hardening exists for (Sumit,
Priya, IntelliAI, QwikCart, currency, %, dates, phones, speeds, the
male voice, the legacy alias) plus the refusal rows (empty,
over-limit, invalid voice, unauthorized) at their exact status codes.
English voice ids, chunking (Latin split byte-identical — test-
pinned), streaming, billing, and playback are all pinned green in the
suites (api 668, tts-runtime 170). The English G2P path is untouched
by construction: the Hindi component is a separate class behind a
per-voice-language branch, and the English normalization pack is
selected exactly as before for every `en` voice.

## 12. Speech Studio + playback (Phases 11, 20)

The voice dropdown now mirrors the DEPLOYMENT: rebuilt from
`GET /v1/audio/voices` after key connect — a staging stack lists
Hindi Female/Hindi Male, production keeps exactly the English pair
(the served page hardcodes no Hindi option). A Hindi voice swaps the
example placeholder to Devanagari. **PlaybackSession untouched** —
zero diffs to the M37 state machine; all M37 structural pins green,
`audibleSources ≤ 1` unchanged. Web E2E: §13.

## 13. Local HTTPS Web E2E (Phase 23) — YES

Through Caddy (`https://localhost`, production-shaped stack,
staging registry profile):

- `/console/speech` serves with every M39 marker (catalog-driven
  dropdown, Hindi labels, Devanagari example) and ZERO engine-token
  leaks; `/v1/audio/voices` via the edge lists all six voices.
- `stream:true`, `hindi-female`, a 132-char call-center line
  (greeting + IntelliAI + ₹4,999 + 12/09/2026 + question): **TTFB
  1.38 s, total 3.77 s for 15.4 s of audio** — the edge passes chunks
  through as they arrive, no buffering.
- The delivered stream, round-tripped through the promoted E3 route,
  came back as: *"नमस्ते सुमित इंटेली ए आई में आपका स्वागत है। आपका
  बिल चार हज़ार नौ सौ निन्यानवे रुपये का है और अंतिम तारीख बारह
  सितंबर दो हज़ार छब्बीस है। क्या मैं आपकी ओर मदद कर सकती हूँ?"* —
  brand spoken, currency and slash-date verbalized in Hindi, question
  intact. Evidence: `evidence/m39-web-e2e.json`.
- Founder click-through (2 min, both voices): open
  `https://localhost/console/speech` → pick Hindi Female → Generate →
  speech starts while the rest synthesizes; Pause/Resume/Stop; after
  Completed press the player's play (replay, no network) and
  Download — and `window.__iaiPlayback.audibleSources` stays ≤ 1
  throughout (the M37 observable, unchanged).

## 14. Security / leaks (Phase 21)

hf_alpha/hm_psi/kokoro/espeak never appear on any public surface
(console page pins + voice-listing leak scan + M35 sweeps); user text
never becomes an argv (stdin transport, test-pinned with hostile
inputs); G2P bounded by timeout; artifacts hash-verified at boot; no
request-time downloads; errors keep the public envelope
(`voice_not_found` before any plane crossing in production; G2P
failure = ordinary internal error, engine-vocabulary-free).

## 15. Smoke (Phase 22)

`make tts-smoke`: version floor **0.4.0** (a pre-M39 image FAILS),
`hindi_g2p` posture key required, and the voice law both ways —
component declared ⇒ both Hindi voices served; not declared ⇒ neither.
Gateway synthesis now proven in BOTH languages (English trap sentence
+ Hindi sentence with ₹/date through the real key path). Production
smoke unchanged (no TTS in prod.yml at all).

## 16. Tests

tts-runtime **170** (new: 24 Hindi — G2P parity/boundary/mapping,
danda chunking, engine routing, voice gating, pipeline language
routing; 22 Hindi normalization) · api **668** (new: registry
proposal suite 13, gateway Hindi suite 4; console M39 pins; ops pins
updated) · mypy strict clean · ruff clean.

## 17. Limitations / next

- Romanized Hinglish ("aap kal office aaoge") is NOT transliterated —
  it rides the voice's pipeline as-is (M38-measured behavior;
  transliteration is its own future milestone).
- Bare clock times without AM/PM pass through normalization v1.
- Naturalness remains the founder's axis: the M38 audition pack
  (UNSCORED) is still the listening protocol; C-grade upstream voices
  are the known ceiling until E-TTS-1.
- Production promotion is NOT this milestone: the route proposal
  carries the PENDING sentinel; promotion = the M26-style commit
  (catalog diff + founder decision reference), plus the TTS production
  launch gate itself (Hostinger, prod overlay, seed-models — all
  untouched here).
- Android/iOS remain whole-body English clients; additive contract
  unchanged for them.

## 18. The M39 spec's final answers

1. **Hindi TTS implemented?** YES — both approved voices through the
   full existing architecture, staging-gated, zero failures on the
   61-probe battery.
2. **Long-text truncation?** FIXED — measured gone at every ladder
   length through the production path (§9).
3. **English broken?** NO — 23/23 M35 battery, byte-identical Latin
   chunking, all suites green (§11).
4. **Streaming?** PASS — length-independent TTFA 0.5-1.6 s, up to
   29.9× better than whole-body (§10).
5. **Production?** Untouched: live catalog refuses, prod refuses the
   staging profile, prod.yml has no TTS, smoke floors enforce images.
