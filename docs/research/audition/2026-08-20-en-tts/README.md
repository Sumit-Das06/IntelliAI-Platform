# English TTS Audition — M33 listening pack

**Purpose.** Side-by-side human listening for the M33 English TTS
decision. Automated metrics (round-trip WER, RTF, RAM) are already in
[the M33 report](../../2026-08-20-english-tts-model-selection.md);
**naturalness is decided by ears, not by proxies** — nothing in this
pack is ranked until a real listener scores it.

**Where the audio is.** WAVs are NOT committed (repo law: audio never
enters git). The manifest below lists every sample with its SHA-256 so
a listener can verify they are hearing exactly the benchmarked bytes.
Local copies live at the session scratchpad
(`…\scratchpad\m33-audition\`) and in WSL under `~/m33/audition/`;
regenerate any sample with the M33 harness (same probe ids, pinned
revisions) if the local copies are gone.

## Candidates in this pack

| Label | Engine | Voice | Revision / artifact |
|---|---|---|---|
| A | Kokoro-82M (production path, espeak-free) | reference-alto (af_heart) | kokoro-82m v1 (repo-pinned shas) |
| B | Magpie-TTS Multilingual 357M via NeMo-Speech.cpp (CPU GGUF) | John (and one female, Sofia) | GGUF v2602 f16 via the runtime's verified pull |
| C | Chatterbox-nano 110M | — | **ABSENT from this pack**: no released library can load nano (M33 packaging finding); slot reserved for when upstream ships the loader |
| D | Supertonic 3 (99M ONNX) | M1 | supertonic-3 via PyPI 1.3.1 |

Identical texts across all candidates (ids from
`research/experiments/33-english-tts-selection/probe-texts-en-v1.json`):
`en-general-01` (normal), `m32-en-paragraph-01` (call-center paragraph),
`m32-en-brand-01` (the "IntelliAI/Kavya" OOV trap), `m33-pros-howq` /
`m33-pros-howq-bare` ("How are you?" vs "How are you."),
`m33-en-mixedpunct-01` (mixed punctuation).

## Listening form (score 1-5; one row per candidate per text)

| Text id | Candidate | Naturalness | Pronunciation | Prosody | Intelligibility | Overall | Notes |
|---|---|---|---|---|---|---|---|
| | | | | | | | |

Guidance: Naturalness = "would a caller notice it is synthetic?";
Pronunciation = names/acronyms/brand words spoken correctly; Prosody =
pauses, question rise, emphasis; Intelligibility = every word
recoverable without effort. Do not average across texts mentally —
score each row, the analysis aggregates.

## Status

**UNSCORED — no human listening has been performed in M33.** All
quality-adjacent claims in the M33 report are therefore intelligibility
(machine round-trip) facts, and naturalness remains UNKNOWN until this
form has real rows. Manifest with SHA-256 per sample:
[manifest.json](manifest.json).
