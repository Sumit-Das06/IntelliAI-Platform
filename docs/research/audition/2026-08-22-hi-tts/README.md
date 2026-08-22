# Hindi TTS Audition Pack — M38 (2026-08-22)

Human-listening pack for the M38 Hindi TTS model selection. Machine
round-trip numbers (RT-WER/RT-CER through the E3 judge) are recorded in
`docs/research/2026-08-22-hindi-tts-model-selection.md`; **this pack is
the naturalness axis those numbers cannot measure**. Nothing here is
scored until a human listens — per the research framework, machine WER
is never called "naturalness".

## Where the audio lives

WAV files are NEVER committed (audio never enters git). The pack is
assembled at the session scratchpad under `m38-audition/`, mirrored from
the WSL research runs (`~/m38/audio/`). Regenerate any time with the
M38 harness (`research/experiments/38-hindi-tts-selection/harness/`).

Layout: `m38-audition/<engine-voice>/<probe-id>.wav`

## Candidates in the pack

| Folder | Engine | Voice | License posture |
|---|---|---|---|
| `kokoro-hi-hf_alpha` | Kokoro-82M, espeak-ng `hi` G2P (research path) | hf_alpha (F, upstream grade C) | Apache weights; GPL espeak binary at exec boundary (M35-blessed shape) |
| `kokoro-hi-hf_beta` | same | hf_beta (F, grade C) | same |
| `kokoro-hi-hm_omega` | same | hm_omega (M, grade C) | same |
| `kokoro-hi-hm_psi` | same | hm_psi (M, grade C) | same |
| `supertonic-hi` | Supertonic 3 (99M ONNX) | F1 preset | code MIT; **weights OpenRAIL-M — REVIEW REQUIRED** |

**Excluded from the pack**: SPRINGLab F5-Hindi — its cloning-style
interface means every output mimics the reference audio, and the M38
research reference was one of our own SYNTHETIC Kokoro WAVs (the
consent-clean choice). Auditioning it would score the reference, not
the model; its intelligibility/latency numbers live in the M38 report.

## Audition texts (same texts across every candidate)

| Probe id | Category | Why it is in the pack |
|---|---|---|
| `m38-spec-name-q` | question | short greeting + question contour |
| `hi-general-01` | general | everyday sentence, mixed marks |
| `m38-spec-price` | currency | ₹12,500 — number verbalization |
| `m32-hi-dates-01` | dates | date reading |
| `m32-mixed-cc-04` | code-switch | Devanagari + English tokens |
| `m38-exclaim-01` | exclamation | excitement rendering |
| `m38-places-01` | place names | Indian city names |
| `m32-hi-paragraph-01` | paragraph | sustained speech, danda pacing |

## Rubric (per candidate, per listener)

Scores are 1-5. **Nobody has listened yet — every cell is UNSCORED.**

| Candidate | Naturalness | Intelligibility | Pronunciation | Prosody | Voice quality | Overall |
|---|---|---|---|---|---|---|
| kokoro-hi hf_alpha | UNSCORED | UNSCORED | UNSCORED | UNSCORED | UNSCORED | UNSCORED |
| kokoro-hi hf_beta | UNSCORED | UNSCORED | UNSCORED | UNSCORED | UNSCORED | UNSCORED |
| kokoro-hi hm_omega | UNSCORED | UNSCORED | UNSCORED | UNSCORED | UNSCORED | UNSCORED |
| kokoro-hi hm_psi | UNSCORED | UNSCORED | UNSCORED | UNSCORED | UNSCORED | UNSCORED |
| supertonic-hi F1 | UNSCORED | UNSCORED | UNSCORED | UNSCORED | UNSCORED | UNSCORED |

Protocol (same as the M3/M33 audition discipline):

1. Listen blind where possible (shuffle folders, name them A-E).
2. Score each axis independently; do not average in your head.
3. The launch question is written down BEFORE listening: *"Would you
   put this voice in front of a paying call-center customer?"* —
   yes/no per candidate, recorded next to the scores.
4. Results append to the M38 report and the model ledger; they never
   overwrite the machine numbers.
