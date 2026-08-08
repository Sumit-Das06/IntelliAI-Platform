# ADR-0028: Datasets as logical definitions over immutable versioned snapshots

- **Status:** Accepted
- **Date:** 2026-08-08
- **Related:** ADR-0010, ADR-0021, docs/FINE_TUNING_STRATEGY.md

## Context

The flywheel stores consented speech samples with immutable originals,
evolving corrected transcripts, and append-only lifecycle events
(Commit 8–10). The fine-tuning strategy is decided in outline —
pretrained multilingual STT → curated IntelliAI data → fine-tune →
evaluate → promote — but no checkpoint is chosen and no training
infrastructure exists. What is missing is the step between "samples
exist" and "training happens": a way to say *which* samples constitute
a training corpus, such that a run executed months later can name its
inputs exactly.

Two facts shape the design. First, `current_transcript` legitimately
changes after collection (corrections are the product's whole point),
so "the samples matching filter F" is a moving target. Second, audio
objects are large and canonical; transcripts are small and mutable.

## Problem

How do we define training corpora today so that a future fine-tuning
run is exactly reproducible — same members, same training text — while
samples keep evolving and without copying audio?

## Decision

We will separate the **Dataset** (a logical definition: name +
validated criteria over the organization's samples) from the **Dataset
Version** (an immutable snapshot: the samples that matched at one
moment, with per-member pinned `training_transcript`). Membership
references the canonical `speech_samples` row — audio is never copied;
only the transcript, the one mutable training-relevant fact, is pinned
at freeze time.

Versions are frozen in a single transaction: lock the dataset row,
number the version (`max+1`, backed by a uniqueness constraint), insert
membership as one `INSERT … SELECT` from **the** eligibility query, and
compute the stored aggregates *from the membership just written*. There
is exactly one eligibility implementation — the preview endpoint wraps
the same query the freeze inserts from — so the preview can never
promise a membership the freeze does not deliver.

No verb updates or deletes a version or its membership. New samples and
later corrections are expressed as the *next* version. Freezing appends
`included_in_dataset` to each member's event history (the vocabulary
the event system reserved) and deliberately does not touch sample
`status` — `training` remains reserved for actual future training runs.

Eligibility is computed from database state only: org scope, lifecycle
not `rejected`/`archived`, non-zero audio bytes and seconds, a
non-blank current transcript, and the consent snapshot (structurally
present on every stored sample; the predicate is executable
documentation). Criteria are the dimensions the samples actually carry:
language (detected, else requested — the console's own definition),
client source, corrected (`current != original` — the console's own
badge), and collection date range.

## Alternatives considered

- **Resolve membership at training time from criteria.** Rejected: a
  correction or new sample between "decide" and "train" silently
  changes the corpus; two runs from "the same dataset" become
  incomparable, which defeats evaluation-gated promotion.
- **Snapshot full sample rows (or audio) into the version.** Rejected:
  duplicates what is already immutable (audio bytes, provenance) and
  bloats storage for zero reproducibility gain; the sample row is the
  canonical record and privacy erasure must reach every copy anyway.
- **Pin transcripts by event-time reconstruction** (replay corrections
  up to the freeze timestamp). Rejected: correct but expensive and
  clever; a pinned text column is the same truth, readable with a JOIN.
- **Require `status = accepted` for eligibility.** Rejected for now: no
  review workflow promotes samples yet, so every version would freeze
  empty. The rule lives in one place and tightens when review ships.
- **Sample-count/duration as live queries on version reads.** Rejected:
  stored aggregates computed from the frozen membership are the frozen
  truth; live recounting would drift the moment erasure shrinks a
  version, hiding exactly the fact an auditor needs to see.

## Trade-offs

- A version's pinned transcripts go stale relative to later corrections
  — by design; freshness costs one POST (the next version).
- Membership rows cost one row per (version, sample); versions over the
  same samples multiply rows. Acceptable at cohort scale; a future
  export format can compact.
- Privacy erasure CASCADEs through membership, so an old version can
  shrink below its stored `sample_count`. We accept the discrepancy as
  an honest record that erasure happened (the stored aggregates say
  what was frozen; the rows say what remains).

## Consequences

- A future fine-tuning run references one `dataset_version_id` and gets
  members, pinned training text, audio references, languages, client
  sources, durations, and provenance via one JOIN — no schema change.
- The lineage chain Model → Run → **Dataset Version → Speech Sample →
  original audio + transcript history** has its bottom half; run tables
  attach to versions later, additively.
- Datasets never delete — `archived` retires them from active work
  while versions stay readable forever (training lineage law).
- The eligibility rules live in exactly one repository method; every
  future consumer (export, training, review tightening) must reuse it
  or re-fight this ADR.

## Future review criteria

- A review workflow ships (samples reach `validated`/`accepted`):
  tighten eligibility to review-gated states in the one query.
- Versions at ≥10⁶ membership rows or freeze transactions measurably
  blocking collection writes: revisit freeze batching/async creation
  (a `status` column on versions would then arrive additively).
- A legal erasure regime requiring versions to record *that* members
  were erased (not merely shrink): add tombstone accounting then.
