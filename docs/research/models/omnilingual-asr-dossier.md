# Omnilingual ASR (Meta) — Gate 0 Intake Record

| | |
|---|---|
| **Stage** | Gate 0 — intake only. No screening, scoring, comparison, or recommendation. |
| **Status** | Researching |
| **Registered** | 2026-08-04 (ledger seed) · intake record created 2026-08-05 |
| **Capability** | transcription |

> Fields are **claims** (§2) unless marked *verified at source*.

## Lineage
Omnilingual ASR — Meta's massively-multilingual speech recognition
effort, the successor line to its earlier multilingual speech work.
**Important lineage caution:** Meta's neighbouring speech releases (MMS,
SeamlessM4T) are CC-BY-NC and therefore unusable to us, so licence facts
must be established **per repository**, never inherited from the org.

## Repository
Meta AI / `facebookresearch` distribution; checkpoints on HuggingFace.
Exact repo to be pinned at Gate 1.

## Organization
AI at Meta (FAIR). High research output; open-weight licensing has been
inconsistent across its speech portfolio.

## License (claimed at intake)
Apache-2.0 — recorded in the 2026-07-31 sweep. **Not re-verified at
source in this intake.** Given the org's mixed record (see above), this is
the single highest-value verification in this lineage's Gate 1.

## Model family / sizes
Multiple sizes claimed; not pinned at intake.

## Supported languages (claimed)
1,600+ languages — by far the widest claimed coverage in this intake.
Includes long-tail Indic languages no competitor covers, and plausibly
Arabic varieties, though dialect-level quality is entirely unestablished.

## Streaming support (claimed)
Not established at intake.

## Hardware expectations
Unknown. The `fairseq2` stack is known operational friction rather than a
hardware property.

## Maintenance activity
Active as research; long-term product commitment to any single checkpoint
is uncertain, consistent with Meta's research-release pattern.

## Commercial concerns
Licence verification is the gating concern (above). Beyond that, `fairseq2`
integration cost is a real serving consideration against our runtime
architecture.

## Known limitations
English competitiveness is reportedly not the goal; integration friction;
breadth is claimed at the language *count* level, which says nothing about
per-language quality — exactly the kind of claim our per-language evidence
bar (§7) exists to discipline.

## Why this lineage deserves investigation
It is the only candidate whose coverage claim could serve **long-tail
languages beyond EN/HI/AR** — a strategic asset if IntelliAI's language
policy ever widens, and a possible source of Arabic dialect coverage.
Investigating it is cheap (desk work) and the licence question alone is
worth answering definitively.
