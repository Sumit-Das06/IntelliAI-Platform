# Security Guidelines

Judgment rules for a commercial multi-tenant platform holding customer
audio and credentials. Mechanical enforcement (secret scanning, dependency
locks, non-root containers, SecretStr masking) is already wired into hooks,
CI, and the type system — this document is the thinking that tooling can't
do for you.

## The mindset

Customer data (audio, transcripts, usage patterns) is radioactive: hold as
little as possible, for as short as possible, visible to as few code paths
as possible. Every feature design starts with "what does this expose, and
to whom?"

## Secrets

- Environment variables are the only channel; `SecretStr` in code; unwrap
  at the last possible moment; never store the unwrapped value.
- Secrets never go in: logs, URLs, error messages, git, Docker images,
  code comments, or chat messages. **A credential pasted into a chat,
  ticket, or screenshot is compromised — rotate it immediately, without
  debate.** Rotation is cheap; hope is not a control.
- Dev credentials (`.env`) are throwaway by design and still never reused
  anywhere else.

## Tenant isolation

- Organization identity derives from the authenticated API key —
  **never** from a client-supplied ID, header, or body field.
- Every repository method touching tenant data takes explicit org scope
  (ADR-0010). Cross-tenant reads are the platform's worst-case bug class:
  treat any doubt as a release-blocker.
- Public IDs are prefixed and non-sequential; internal integer PKs never
  cross the API boundary (they enumerate).

## Input handling

- All input is validated at the boundary by Pydantic — but validation is
  not sanitization: uploaded filenames, content types, and audio payloads
  are untrusted regardless. Enforce size limits before reading bodies.
- Never build SQL, shell commands, or file paths from client input; the
  repository layer and typed APIs exist so you never have to.

## Dependencies

A new dependency is an audit, not an import: license (permissive only —
the model-license policy of ADR-0005 applies in spirit to code), health
(maintained? release cadence?), and blast radius (what does it pull in?).
Prefer the standard library; prefer boring.

## When something goes wrong

Suspected leak or breach: rotate affected credentials first, assess second,
write up third (what, when, blast radius, fix) — in that order. The
request-ID-correlated logs exist precisely so the assessment is evidence,
not guesswork. No blame culture: the write-up targets the system that
allowed the mistake, and usually ends in new tooling, not new vigilance.

## Not in this document

Compliance roadmap (SOC 2, DPAs) — PRD §9. Auth implementation (key
hashing, prefixes) — designed in M1 with its own review. Tool configs —
they live where they run.
