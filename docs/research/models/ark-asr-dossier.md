# ARK-ASR-3B (Audio8) — Gate 0 Intake Record

| | |
|---|---|
| **Stage** | Gate 0 intake · **Gate 1 verdict: BLOCKED (2026-08-05) — work halted** |
| **Gate 1** | Provenance **resolved** (Audio8 publishes; AutoArk is the research origin; card is canonical). Licence `apache-2.0`. Blocked on the **executing chain**: mandatory `trust_remote_code` whose code derives from `AutoArk/open-audio-opd`, `THUNLP/OPD`, `volcengine/verl` — none verified. **No Gate 2 dossier until those licences are verified.** [Screening record](../2026-08-05-stt-gate1-license-screen.md) |
| **Status** | Researching |
| **Registered** | 2026-08-05 |
| **Capability** | transcription |

> Fields are **claims** (§2) unless marked *verified at source*.

## Lineage
ARK-ASR — a 2026 audio-LLM ASR entrant: a Whisper-style audio encoder →
MLP adapter → **Qwen decoder**, served through custom `arkasr` remote
code. Architecturally it is a SALM-class model (compare
[canary-qwen-dossier.md](canary-qwen-dossier.md)).

## Repository
`huggingface.co/Audio8/ARK-ASR-3B` — verified to exist, 2026-08-05.

**Provenance flag:** a repository of the same model name also appears
under a second organisation (`AutoArk-AI/ARK-ASR-3B`), which publishes its
own leaderboard-results dataset. Which repository is canonical, and
whether the two are identical, is **unresolved at intake** and must be
settled before any other work on this lineage. Pinning the wrong
repository would make every downstream fact wrong.

## Organization
Audio8 (and/or AutoArk-AI — see above). A young organisation with no
established track record, in contrast to every other registered lineage.

## License (claimed at intake)
**`apache-2.0` — verified at source on the `Audio8/ARK-ASR-3B` card,
2026-08-05.** This verdict covers that card only; if a different
repository proves canonical, the verdict does not transfer.

## Model family / sizes
3B parameters.

## Supported languages (claimed)
19 languages: Chinese, English, German, Japanese, French, Korean,
Spanish, Polish, Italian, Romanian, Hungarian, Czech, Dutch, Finnish,
Croatian, Slovak, Slovene, Estonian, Lithuanian.
**No Hindi. No Arabic.**

## Streaming support (claimed)
None stated on the card.

## Hardware expectations
3B with an LLM decoder — GPU-oriented; the least CPU-aligned size class
alongside Canary-Qwen.

## Maintenance activity
New; no release history to assess.

## Commercial concerns
Two independent flags beyond the licence itself:
1. **Custom remote code** (`arkasr`, requiring `trust_remote_code`-style
   execution) — running vendor code inside our runtime process conflicts
   with the weights-import hygiene discipline the platform already
   applies, and would need real security review, not a licence check.
2. **Inherits a Qwen decoder**, so Qwen concentration considerations
   partially apply even though the publisher is unrelated.

## Known limitations
No Indic or Arabic coverage; unproven organisation; remote-code
dependency; leaderboard-topping claims from a new entrant warrant the
scepticism our epistemic discipline mandates — the claim is recorded here,
not credited.

## Why this lineage deserves investigation
It currently sits at the top of the public English short-form leaderboard,
and a candidate claiming state-of-the-art English accuracy under Apache-2.0
is worth *understanding* even when its deployment shape (3B, GPU, remote
code) is poorly matched to ours. Gate 0 asks only whether the lineage
deserves investigation; the honest answer is yes — with provenance and
remote-code questions as the first things to resolve, and with the
expectation that they may end the investigation quickly.
