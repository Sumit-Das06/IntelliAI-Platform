# Cohere Transcribe (2B, general) — Gate 0 Intake Record

| | |
|---|---|
| **Stage** | Gate 0 — intake only. No screening, scoring, comparison, or recommendation. |
| **Status** | Researching |
| **Registered** | 2026-08-05 |
| **Capability** | transcription |

> Fields are **claims** (§2) unless marked *verified at source*.

## Lineage
Cohere Transcribe — the general multilingual member of Cohere's
open-weight ASR line, released March 2026. Its Arabic sibling is
documented separately in
[cohere-transcribe-arabic-dossier.md](cohere-transcribe-arabic-dossier.md).

## Repository
`huggingface.co/CohereLabs/` (exact repo id to be pinned at Gate 1).

## Organization
Cohere / Cohere Labs — a commercial lab with a paid transcription API
alongside the open weights, i.e. open weights are a strategy here, not a
byproduct.

## License (claimed at intake)
Apache-2.0 (claimed; landscape material and the 2026-07-31 sweep agree).
**Not verified at source in this intake** — the Arabic sibling *was*
verified Apache-2.0 on 2026-08-05, which raises confidence but does not
transfer: per-artifact-version verdicts are law, and this org has shipped
CC-BY-NC weights on other product lines.

## Model family / sizes
2B parameters, encoder-decoder (FastConformer-class encoder with a
lightweight decoder, consistent with its Arabic sibling).

## Supported languages (claimed)
Multilingual; the specific language list and whether **Hindi** or Arabic
appear in the general model are unresolved at intake and are a Gate 2
question. If the general model covers Hindi *and* the Arabic sibling
covers Arabic, one organisation's lineage could serve two of our three
product languages with one serving stack.

## Streaming support (claimed)
Not established at intake.

## Hardware expectations
2B; same class as its Arabic sibling. CPU viability unknown.

## Maintenance activity
Active: general model March 2026, Arabic model July 2026 — an ongoing
line rather than a single release.

## Commercial concerns
Same licence-divergence watch as the Arabic sibling. Additionally, the
vendor operates a competing commercial transcription API, which is
neutral for licence purposes but worth noting when assessing how long
weights stay open.

## Known limitations
Single-generation track record; language list unconfirmed; no streaming
claim; the leaderboard position it debuted with has already been overtaken
by later entrants — a fact about the landscape's pace, not a quality
judgment (none is made at Gate 0).

## Why this lineage deserves investigation
It is a **recent, permissively-licensed, deliberately small generalist**
from a lab that is actively maintaining the line — and the only lineage in
this intake with a purpose-built Arabic sibling. That combination makes it
worth understanding as a potential *two-language* answer rather than as
one more English model.
