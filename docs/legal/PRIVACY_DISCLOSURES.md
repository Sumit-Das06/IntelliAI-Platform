# Privacy Disclosures — Behavior-to-Disclosure Map

> **DRAFT — REQUIRES LEGAL COUNSEL REVIEW BEFORE ANY PUBLIC USE.**
> Nothing in this file is approved legal text. It is the engineering
> inventory of what the platform *actually does*, written so counsel can
> draft a privacy policy that is true. Every claim below is enforced by
> code and tests at commit time; if behavior changes, this file must
> change in the same commit.

## Why this file exists

A privacy policy that promises less collection than happens is a legal
violation; one that promises more restraint than the code enforces is a
lie waiting for discovery. This map keeps the policy tethered to the
implementation. The one sentence the product must never say:
**"your data is never used for training"** — organization consent plus
contribution can make it so.

## What must be disclosed, because the code does it

### Voice capture and transcription (both clients)

- The microphone records **only between an explicit start and stop**
  (keyboard: tap mic/tap stop, 60 s hard cap; Studio: record button).
- Audio is sent to the configured IntelliAI server **for
  transcription** and a transcript is returned. On the keyboard, audio
  lives only in memory and is never written to device disk.
- Typed text on the keyboard is **never** logged, stored, or
  transmitted.
- Request metadata (duration seconds, language, timestamps, client
  type, request ids) is retained in the usage ledger for **billing and
  operations**, regardless of any training consent. It contains no
  audio and no transcript text.

### Training-data collection (the flywheel)

Stored **only when all gates pass**: the deployment allows collection,
the **organization** has explicitly opted in (`data_consent`,
recorded with timestamp and governing document), and the **request**
did not opt out (keyboard toggle / Studio checkbox →
`X-IntelliAI-Contribution: off`). When stored: the original audio,
machine transcript, any human corrections, language and client
metadata, and a snapshot of the consent it was collected under. Purpose:
**improving IntelliAI STT**. Stored samples may be frozen into dataset
versions and training manifests.

### Corrections

A user-submitted correction is stored alongside the sample (original
machine transcript preserved separately) — only for collected samples;
correcting is impossible when nothing was stored.

### Rights and retention (pilot shape)

- Erasure exists and is operator-executed: per sample, per person
  (one-key-per-person convention), or whole tenant
  (`docs/DATA_GOVERNANCE.md` is the authoritative mechanics).
- Usage-ledger records are retained as commercial records and survive
  erasure (no content, only metering facts).
- Backups age erased data out within the 14-night retention window.
- Data resides on the deployment's infrastructure (region is a
  deployment decision — **counsel: data-residency statement needed once
  the VPS region is chosen**).

## Documents that must exist before public launch (none exist yet)

1. **Privacy policy** (public URL — Play Store requires it; DPDP
   requires meaningful notice). Source material: this file.
2. **Organization consent document** — what a tenant actually signs
   when granting `data_consent`; its reference string is what operators
   record via `make grant-consent ref=…`.
3. **Play Data Safety mapping** — see `apps/keyboard-android/RELEASE.md`.

## Where the in-app wording already lives (must stay consistent)

- Keyboard: contribution toggle + explanation, privacy line in setup
  (`apps/keyboard-android/app/src/main/res/values/strings.xml`).
- Studio: permanent consent notice + contribution checkbox
  (`apps/api/src/intelliai_api/static/console/studio.html`).
