# Hindi Evaluation Corpus Specification v1

| | |
|---|---|
| **Status** | v1 — the permanent specification every future Hindi evaluation follows |
| **Proposed corpus name** | `stt-hi-eval` (versioned; the name is ratified at v1 release, never changed after) |
| **Standing law inherited** | A corpus version is **immutable the moment a result cites it**. References are stored **verbatim — no normalisation at creation**. `publication_status: private`, `contamination_risk: none_known` — this corpus is built by us and **never published**, which is the only structurally clean position. Consent and licensing are gating properties, not metadata. |

## 1. Purpose

This corpus is the instrument that answers, with evidence rather than anecdote:

1. **How well is Hindi actually served today?** (the Stage 3 production decision)
2. **Where exactly does it fail?** — the error profile by class (sub-word/matra, whole-word, entities and numerals, code-mixed speech), which is what selects any remedy
3. **Did anything change?** — regression testing for every future Hindi release, forever
4. **Later, with its own rules (§6): what should improvement train on?**

One corpus, designed once, because retrofitting a corpus means re-buying every number ever measured on it.

## 2. Scope — what Hindi must be represented, and why

| Category | Why it exists |
|---|---|
| **Spontaneous conversational Hindi** | The dominant real traffic shape; unscripted speech carries the disfluencies, speed, and reductions that read speech hides |
| **Read / prepared Hindi** | The controlled anchor: known text, clean delivery — separates "hard audio" errors from "hard language" errors |
| **Formal register** (news-style, announcements) | Vocabulary and cadence differ from conversation; a service sold to businesses will receive it |
| **Hinglish (code-mixed)** | A defining property of real Indian speech; measured as its own slice so its numbers never dilute or inflate the monolingual reading |
| **Numbers, dates, currency, addresses** | The highest-value tokens in business transcription (orders, bookings, invoices); also where two numeral systems (Devanagari and Arabic digits, spoken either way) collide |
| **Personal and place names** | Proper nouns are the classic recognition weakness and the most customer-visible one |
| **Technical words and abbreviations** | SaaS customers speak product names, units, and acronyms; abbreviation pronunciation is a known ambiguity class |
| **Matra / conjunct-dense content** | The one Hindi error ever observed in production (लगता → लकता) is a matra-class error; the corpus must contain enough diacritic-dense material to measure that class, not just meet it by chance |
| **Clean indoor audio** | The majority reference condition; every other condition is read against it |
| **Noisy environments** (street, café, household) | Real users do not record in studios |
| **Telephone-quality audio** (narrowband, 8 kHz-originated) | Call-center and telephony integrations are a primary commercial use |
| **Outdoor recordings** | Wind and open-air acoustics; distinct from indoor noise |
| **Regional accent variation** | Hindi across the belt (e.g., Delhi/UP, Bihar-adjacent, MP/Rajasthan, Mumbai-influenced) varies enough to matter; a one-region corpus measures one region |

## 3. Dataset Structure

### C1 — fast engineering corpus (10–20 clips)

**Purpose:** prove the pipeline end to end (recording → registration → hashing → scoring) and give an early, cheap signal of the error landscape within days. **Composition:** 3–5 speakers, mixed gender, mostly clean audio, at least 2 Hinglish clips, at least 2 numeral-bearing clips, plus the probe set (§7). **Limitations, stated on the manifest itself:** supports **no quality claim** (below the ≥100 floor), no coverage guarantees, no accent balance. C1 clips **may** be carried into C2 byte-identically (overlap permitted, identity not — C1 stays deliberately small and stable).

### C2 — production evaluation corpus (≥100 clips)

The decision-grade instrument. Hard requirements:

| Axis | Requirement |
|---|---|
| Size | ≥100 natural-speech clips (≥120 recommended so slice minima hold) |
| Speakers | ≥10, pseudonymous roster (SPK-NN), no speaker >15% of clips |
| Gender | ≥40% / ≥40% either way |
| Age spread | at least three decade bands represented |
| Accent | ≥3 distinct Hindi-belt regions, each ≥10% of clips |
| Style | spontaneous ≥40% · read ≤30% · formal/prepared the remainder |
| Noise | clean ≥50% · noisy 20–30% · telephony ≥10% · outdoor ≥5% |
| Hinglish slice | 15–25% of clips, tagged code-mixed, **separately reported forever** |
| Duration mix | <5 s ≥15% · 5–15 s ≈50% · 15–60 s ≈25% · >60 s ≥5% |
| Content minima | numerals ≥15 clips (both numeral systems, both spoken styles) · dates/currency ≥8 · addresses ≥5 · personal/place names ≥10 · technical/abbreviations ≥5 · matra/conjunct-dense ≥15 |
| Probes | the full §7 probe set |

Per-clip attributes (speaker id, style, condition, region, code-mixed flag) are carried in a structured, machine-readable notes convention defined in the convention sheet — no new schema is minted for v1; a future additive field may replace the convention without touching any clip.

## 4. Clip Requirements

- **Natural human speech only.** No synthetic speech, no TTS, no re-recorded playback of other recordings, no broadcast/rights-encumbered material. Every clip is recorded by us or by a consenting speaker for us.
- **Duration:** 2 s minimum, 120 s maximum per clip (long-form ≤ the product's 600 s ceiling; the >60 s band satisfies long-form coverage).
- **Sample rate:** recorded at ≥16 kHz (the platform's canonical rate); 44.1/48 kHz originals welcome — never upsampled to fake quality. Telephony clips are genuinely narrowband, not simulated by filtering unless the simulation is documented on the clip.
- **Formats:** lossless preferred (WAV/FLAC); phone-native compressed formats (M4A/OGG) accepted for authenticity of the noisy/telephony slices, format recorded per clip. Mono preferred; stereo folded to mono at ingestion.
- **Silence budget:** ≤2 s leading, ≤2 s trailing; internal pauses natural, but total non-speech ≤30% of the clip.
- **One primary speaker per clip**; genuine multi-speaker clips are permitted only as explicitly tagged cases with per-segment speaker ids from the roster.
- Every clip is content-hashed (sha256) at ingestion; the hash is the identity.

## 5. Annotation Rules

References are produced by fluent Hindi speakers, **double-transcribed independently and reconciled**; the disagreement rate is computed and recorded in provenance (it bounds the error floor any measurement can claim). The full convention sheet is versioned **with** the corpus; its governing rules:

- **Verbatim, always.** The reference is what was said — not what should have been said. No grammar correction, no tidying.
- **Script follows the word.** Hindi words in Devanagari. English lexical items spoken as English → Latin script. Assimilated loanwords in everyday Devanagari use (बस, स्कूल, ट्रेन…) → Devanagari, per a fixed loanword list in the convention sheet. Reconciliation resolves edge cases; resolutions are appended to the list, never improvised per clip.
- **Numerals as words, exactly as spoken.** "पचपन" not "55"; "fifty-five" (Latin) if spoken in English. Digits never appear in references — a digit is a normalisation choice, and references are pre-normalisation by law.
- **No punctuation** in `reference_text`. Speech has none; adding it imports transcriber variance.
- **Fillers are transcribed**, from a fixed filler lexicon (अं, हाँ, अच्छा as filler, "um", "uh" …) — verbatim law applies to hesitation too.
- **Repeated words are transcribed as many times as spoken.**
- **False starts:** the fragment is transcribed as heard with a trailing dash (जा- for an abandoned जाना). The convention sheet documents that scoring treats fragments as ordinary tokens after normalisation.
- **Self-corrections:** both the error and the correction are transcribed, in order, verbatim.
- **Laughter, coughs, and non-speech events are NOT words** and never appear in `reference_text` (a bracketed tag would survive normalisation as a fake word). They are recorded in the clip's structured notes.
- **Background speech** from non-primary speakers is not transcribed; its presence is a clip attribute. If background speech is prominent enough to be transcribable, the clip belongs in the multi-speaker case or is rejected.
- **Unintelligible speech:** if any span remains unresolvable after double transcription and reconciliation, the **clip is rejected** from C2 — an evaluation reference must be certain. Rejection counts are recorded.

## 6. Evaluation Splits — and the wall between evaluating and training

**The v1 corpus is 100% evaluation (Test) plus Probe.** There is no train or validation split inside it — an evaluation corpus is a ruler, and rulers are not training data.

The permanent guarantees for the day training data is collected:

1. **A clip cited by any committed evaluation record is permanently barred from any training set** — enforced by content hash (sha256), not filename, so a renamed or re-encoded copy is still caught.
2. **Speaker-level disjointness:** speakers on the evaluation roster never contribute training audio. Voice identity leaks even when clips differ.
3. Training and validation splits live in **separate, future corpus lineages** with their own manifests; nothing in this corpus is ever re-labelled into one.
4. **Future expansion** (new evaluation clips) enters as a new corpus *version* (§9), inheriting every rule here.

## 7. Probe Set

Probes carry `reference_text: ""` — the correct output is silence, and **every word emitted against them is a measured failure**. Five probes minimum:

| Probe | Purpose |
|---|---|
| **Silence** (10 s, generated) | The classic invented-text failure mode; also exercises the platform's silence gating |
| **Pure tone** (440 Hz, 5 s, generated) | Energy without speech — passes naive gating, so it tests behaviour on non-speech *audio*, not just absence of audio. Already proven to discriminate in production-adjacent testing |
| **Music** (self-recorded instrumental snippet — recorded by us for licensing cleanliness) | The most common real-world non-speech input (hold music, ringtones); spectrally speech-like enough to be the hardest probe |
| **Background noise only** (street/café ambience, self-recorded) | Real environments without any speech — the "pocket dial" case |
| **Empty microphone / room tone** | What an open, silent mic actually produces (hum, hiss, handling noise) — distinct from digital silence |

Silence and tone are deterministic generated clips; music, noise, and room tone are recorded assets registered like any other clip. The same probe set is carried in **every tier and every future version**, byte-identical wherever possible.

## 8. Acceptance Checklist — release gate for v1

- ☐ Every §3 composition minimum met, counted from the manifest, not estimated
- ☐ Every clip double-transcribed, reconciled; disagreement rate computed and recorded in provenance
- ☐ Convention sheet v1 frozen and versioned alongside the corpus (script rules, loanword list, filler lexicon, fragment rule, rejection log)
- ☐ Every clip content-hashed; manifest validates against the dataset schema; every referenced file resolvable
- ☐ Speaker roster complete: pseudonymous ids, consent basis recorded **per speaker**, consent forms on file
- ☐ PII review passed: no sensitive personal data; incidental private-person names reviewed under the consent policy
- ☐ `publication_status: private` and `contamination_risk: none_known` recorded; the corpus has never left company storage
- ☐ Probe set complete (all five), probe references empty
- ☐ Duration, style, noise, accent, gender, and Hinglish distributions recorded in provenance as measured numbers
- ☐ No synthetic speech anywhere (generated probes are non-speech by construction)
- ☐ Founder sign-off; name and version ratified; **release makes v1 immutable on first citation**

## 9. Future Compatibility

- **Versions are append-only assets.** v1 is never edited, never pruned, never "fixed". A discovered reference error is corrected in v2 with the correction documented; the v1 reading of that clip stays exactly as it was, because committed evidence cites it.
- **Every measurement cites (corpus name, version, hash).** Numbers from different versions are never merged or directly compared — a new version re-anchors its own readings. This is what makes it safe to grow the corpus without poisoning history.
- **Carry-forward rule:** clips crossing versions are carried **byte-identical** (same hash, same reference), so continuity is verifiable, not asserted.
- **Growth directions:** new versions may add clips, conditions, regions, or content classes; the probe set persists unchanged; the composition table's *minima* may rise but never fall.
- **The convention sheet is versioned with the corpus** — a reference transcribed under sheet v1 is never re-interpreted under sheet v2; a sheet change implies a corpus version boundary.
- **Tier growth:** future adversarial/robustness tiers are separate corpora inheriting this specification's rules, not extensions of the evaluation corpus.

---

*This specification is the permanent contract. Collection, transcription, and release execute it; nothing in it is re-decided per clip, per transcriber, or per release.*
