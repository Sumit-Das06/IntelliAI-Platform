# Data Governance — Collection, Retention, Erasure

> Approved at Milestone 14A (9 Aug 2026) for the **controlled pilot**
> launch shape (Option A: org-issued API keys, one key per person).
> This document is the policy the code implements; the enforcing code is
> `services/erasure.py`, `services/collection.py`, and the schema's
> cascade topology. If this document and the code ever disagree, that is
> a bug in one of them — fix the disagreement, never paper over it.

## The one law

**Privacy outranks reproducibility — and the exception must be loud.**

Everything else in this document is a consequence of that sentence plus
two older laws it composes with:

- collected data must never outlive its tenant (schema: samples CASCADE
  from organizations);
- billing history must never disappear (schema: the usage ledger
  RESTRICTs organization deletion).

## What is collected, and under which gates

A speech sample (audio object + row) is stored only when **all three**
gates pass, in this order (`services/collection.py`):

1. the deployment's collection switch is on and storage exists;
2. the **organization** has granted `data_consent` — the ceiling;
3. the **request** did not opt out (`X-IntelliAI-Contribution: off` —
   the keyboard's toggle and the Studio's checkbox).

Collection failure can never fail a transcription, and absence of
collection is a normal outcome, not an error.

## Identity: who a sample belongs to

`speech_samples.user_identifier` records the acting API key's public id.
Under the pilot's **one-key-per-person convention** (see
`docs/ops/cohort-onboarding.md`), that identifier *is* the person, so a
person's deletion request maps exactly to
`erase-user-data --user-identifier key_…`.

**Known limitation, accepted for the pilot:** if a tenant violates the
convention and shares one key among people, per-person erasure below the
key's granularity is impossible — the remedy is erasing the key's whole
data set. A consumer launch replaces this convention with server-issued
per-user credentials (future milestone); the column is deliberately
surface-neutral so that change is additive.

## Retention

| Data | Retention |
| --- | --- |
| Speech samples (audio + transcripts + events) | Until erased (request or tenant offboarding) |
| Dataset versions / preparations | Until their samples' erasure revokes them, or tenant erasure |
| Usage ledger (seconds, language, lineage, timestamps — no content) | Retained as commercial records; survives all erasure |
| Backups | Newest 14 nightly sets (`docs/ops/backup.md`); erased data ages out of backups within the retention window |

## Erasure

Three operator verbs (CLI, `make erase-*`); deliberately **not** a
public endpoint — erasure is a deliberate, audited act. Self-serve
erasure UI is future work over the same service.

### The sequence (per sample)

1. **Revoke poisoned manifests.** Any READY preparation whose frozen
   version contains the sample has a stored JSONL manifest carrying the
   person's transcript text and audio key. The manifest **object is
   deleted**, the preparation's artifact fields are nulled, its status
   becomes `FAILED` with the machine-readable reason `sample_erased`.
   A later re-preparation honestly fails with
   `membership_count_mismatch` — the version permanently, visibly
   records that it can no longer be trained on as frozen.
2. **Delete the audio object.**
3. **Delete the sample row.** Events and dataset-membership rows follow
   via ON DELETE CASCADE.

**Ordering law: objects before rows.** A crash between steps leaves a
row pointing at a deleted object — visible and retryable. Rows-first
would leave orphaned personal audio with no index pointing at it:
undiscoverable, therefore unerasable. The worse failure mode loses.

**Storage unreachable ⇒ abort, retry later — never "erased".**

### What deliberately survives a sample's erasure

- **Frozen version statistics** (`sample_count`, aggregates): counts,
  not content. Rewriting them would silently edit history; the
  preparation layer tells the present-tense truth instead.
- **Usage ledger rows**: commercial facts with no audio or transcript.
- **Structured log lines** naming the erased sample ids (operational
  audit trail of the erasure itself).

### The reproducibility exception, stated exactly

A `READY` preparation is normally terminal and immutable, and a
re-preparation reproduces byte-identical artifacts. **Erasure is the
single sanctioned event that can revoke a READY preparation.** The
revocation is never silent: status flips to `FAILED` with a named
reason, the checksum fields are nulled, and the manifest object is gone.
Any future training run must therefore resolve its manifest through the
preparation row at run time — never from a cached copy — and will
loudly discover revocation.

### Organization erasure

`erase-org` removes every sample (sequence above), every dataset
definition/version/preparation and their manifest objects, and every
membership; **revokes** (not deletes) every API key; then **anonymizes
and keeps** the organization row (`name → "Erased Organization"`,
consent cleared) because the usage ledger's RESTRICT demands the row
exist. Data dies; the commercial skeleton remains.

**Known limitation, accepted for the pilot:** operator `users` rows
(email + name) are not deleted by org erasure — a user may belong to
other tenants. Per-user erasure is a future verb; pilot operators are
internal staff.

## Disclosure

What these mechanics require the product to disclose to humans is
inventoried in `docs/legal/PRIVACY_DISCLOSURES.md` (draft for counsel).
The in-app wording (keyboard settings, Studio checkbox, consent notice)
must always match this document's actual behavior — never promise less
collection than happens, never claim erasure powers that don't exist.
