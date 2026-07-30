# ADR-0012: API key credential design — format, hashing, verification

- **Status:** Accepted
- **Date:** 2026-07-31
- **Related:** ADR-0009, ADR-0010, ADR-0013 (planned), ADR-0014 (planned)

## Context

API keys are the platform's primary credential (M1 scope: platform
identity, not human auth). They are presented on every request, so
verification cost is a per-request tax. They are bearer secrets: whoever
holds one *is* the organization. PRD §9 commits to: shown once, stored
hashed, prefix-identifiable, instantly revocable, org-scoped.

## Problem

What exact key format, hashing scheme, and verification flow give strong
security at per-request cost, without foreclosing future key classes?

## Decision

- **Format:** `ik_<namespace>_<secret>` where the secret is 43 urlsafe-
  base64 characters from `secrets.token_urlsafe(32)` — 256 bits of CSPRNG
  entropy. Total length 52 for `ik_live_` keys.
- **Namespaces:** `ik_live_` issuable now; `ik_test_`, `ik_service_`,
  `ik_temp_` **reserved** (documented, format-valid, not issuable) so
  future key classes need no format migration and external parsers
  (customers' config validation, secret scanners) can rely on the pattern
  from day one.
- **Hashing:** `HMAC-SHA256(key=pepper, message=full key string)`, hex.
  The pepper is a server-side env secret (`INTELLIAI_AUTH_KEY_PEPPER`,
  required at boot). HMAC rather than ad-hoc `sha256(secret+pepper)`
  concatenation: the standard keyed-hash construction, immune to
  length-extension and concatenation-ambiguity pitfalls, identical cost.
- **Storage:** hash (unique column = the lookup index) + display prefix
  (first 16 chars) + last 4 chars + metadata. Plaintext exists only in the
  creation response.
- **Verification:** structural format check → HMAC → single indexed
  equality lookup → `hmac.compare_digest` re-check → revocation/expiry
  checks. Deterministic hashing is what makes O(1) lookup possible.
- **Purity:** all of the above lives in `core/security.py` as pure
  functions — no I/O, no framework imports, no state (ADR-0014 territory
  begins where this module ends).
- **`last_used_at`** is a named optimization target: synchronous throttled
  writes (≤1/key/minute) now; Redis accumulation (M4), then usage-stream
  rollup, later — all invisible above the repository.

## Alternatives considered

- **bcrypt / Argon2** — rejected, and the reasoning matters: slow hashes
  exist to protect *low-entropy* secrets (human passwords) from offline
  brute force. Our secrets carry 256 bits of machine randomness — offline
  brute force is physically impossible regardless of hash speed — so
  slowness buys nothing and costs everything: ~100 ms/verification caps a
  gateway core at ~10 auth/s, and salted-slow hashes forbid deterministic
  lookup (full-table scan per request). **Standing invariant: this scheme
  is valid ONLY for platform-generated high-entropy secrets. If any
  user-chosen credential ever enters the system, it gets Argon2id — no
  exceptions.**
- **Encryption instead of hashing** — rejected: reversibility is a
  liability (we never need the plaintext back), and it imports key-
  management burden.
- **Stateless signed tokens (JWT-style)** — rejected: statelessness
  prevents instant revocation, which PRD §9 requires; a revocation list
  reintroduces the database anyway.
- **Plaintext storage** — listed for completeness; obviously never.

## Trade-offs

- Single unversioned pepper: rotating it invalidates every key at once.
  Accepted for M1; versioned peppers (hash tagged with pepper-id) are the
  known evolution.
- Fast hash means the *entire* defense rests on secret entropy — hence the
  invariant above, enforced by this module being the only key generator.

## Consequences

- Auth adds one HMAC (~microseconds) + one indexed query per request.
- Support can name keys (`ik_live_a1b2…`, `…x4Kq`) without seeing secrets.
- The format is stable enough to register with secret-scanning programs
  (GitHub leak scanning) — worth doing before public launch.

## Future review criteria

- Enterprise compliance demanding pepper rotation → versioned peppers.
- Any user-chosen credential (console passwords, M6) → Argon2id path,
  separate from this scheme.
- Key volume + auth rate making Postgres lookup a bottleneck → Redis
  read-through cache with revocation invalidation (M4's call).
