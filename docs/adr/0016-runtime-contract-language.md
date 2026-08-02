# ADR-0016: The runtime contract is a permanent transport-free language, not a service API

- **Status:** Accepted
- **Date:** 2026-08-02
- **Related:** ADR-0002, ADR-0003, ADR-0009, ADR-0015

## Context

ADR-0002 forbids inference in the gateway; ADR-0003 committed to one internal
contract per *capability*, not per engine. M2 makes that contract real: the
gateway must call `services/stt-runtime` today, a TTS runtime at M3, and an
open-ended set of future runtimes (OCR, vision, translation, embedding, chat)
without ever containing engine-specific code. Engines will churn (Whisper →
Qwen3-ASR; Kokoro → Chatterbox), transports will evolve (HTTP+JSON today,
gRPC/WebSocket candidates at M8 streaming), and deployment shapes will change
(remote service today, possible in-process runtime later). Meanwhile the
platform bans string-literal capability identifiers (M2 design refinement 7)
and requires gateway and runtimes to ship on independent schedules.

## Problem

Where does the shared language between gateway and runtimes live, what does
it contain, and — more important — what is it *forbidden* to contain?

## Decision

We will maintain `packages/runtime-contract` (`intelliai_runtime_contract`)
as a standalone workspace package that owns **only shared vocabulary and
shared schemas** — the platform's internal API specification expressed as
code. It is versioned by a single integer `CONTRACT_VERSION`, owned by the
contract, never by individual runtimes.

**It contains exactly:**

1. **`Capability`** — a frozen `StrEnum`, the single source of truth for
   capability identifiers platform-wide. No module in any package may use a
   string literal where a capability is meant. Members are **append-only**:
   never renamed, never removed, never reused; a member lands in the same
   change as its capability's schemas, not speculatively.
2. **`RuntimeMetadata`** — operational identity only: `service`,
   `service_version`, `contract_version`. **This model is not allowed to
   grow by convenience.** Every proposed field must answer "is this
   *operational* information about the serving process?" — anything that is
   payload (outputs, usage, model behavior, engine details) is rejected, and
   any addition amends this ADR. Metadata is how operators trace *who
   served*; it is never a transport for business data.
3. **Envelopes** — `RuntimeResponse[OutputT]` (output + `model` + `usage` +
   `timing` + `runtime` metadata) and per-capability request schemas.
   `Usage` is a list of `{unit, amount}` with units drawn from the frozen
   `UsageUnit` enum, so billing vocabulary is contract vocabulary.
4. **`RuntimeErrorType` / `RuntimeErrorResponse`** — the runtime failure
   taxonomy: `invalid_input`, `not_ready`, `overloaded`, `internal`. The
   gateway alone translates these to the public envelope (ADR-0009); the
   taxonomy carries **no HTTP status codes and no retry policy** — retry and
   status decisions are gateway policy informed by the type, not dictated by
   the runtime.
5. **Capability-specific schemas** — today `TranscriptionRequest`,
   `TranscriptionResult`, `TranscriptionSegment`; each future capability
   adds its own module beside them.

**It excludes, permanently:** networking, HTTP types, serialization
machinery beyond the schema layer, logging, retries, authentication,
routing, engine or model references, and imports of FastAPI, SQLAlchemy,
Torch, or any inference library. Its only runtime dependency is pydantic.
The HTTP *binding* of this language (multipart-in/JSON-out for STT,
JSON-in/binary-out with an envelope header for TTS, `X-Request-ID` and
`X-Runtime-Contract-Version` headers) is a property of the services that
speak it, first realized in M2 step 3 — the contract defines *what* is said,
never *how it travels*.

**Evolution rules (the backwards-compatibility contract):**

- All contract models are **frozen** (immutable after validation) and are
  **tolerant readers**: unknown fields are ignored, not errors. A newer
  gateway may send a field an older runtime does not know, and vice versa,
  without breakage during rolling upgrades — and because unknown fields are
  dropped on read, undeclared fields are *useless* to send, which closes the
  side-channel that turns schemas into dumping grounds.
- Changes are **additive with defaults** within a contract version. Removing
  or re-typing a field, changing an enum value, or changing envelope shape
  increments `CONTRACT_VERSION` — a platform-wide event, expected to be rare
  (target: single digits over the platform's life).

**Ownership boundaries** (neither side may leak into the other):

| Gateway owns | Runtime owns |
|---|---|
| authentication & authorization | preprocessing (media pipeline) |
| tenancy | model execution |
| routing & model registry lookup | postprocessing |
| retries & end-to-end request timeout | inference metadata (timing, usage measurement) |
| OpenAI compatibility translation | |
| billing & request accounting | |

The runtime never sees an API key, an organization, or a public API shape.
The gateway never sees an engine, a media pipeline, or a model file.

## Alternatives considered

- **String capability identifiers** — rejected: strings drift ("stt" vs
  "transcription" vs "asr"), typos fail at runtime instead of type-check
  time, and renames become unfindable. An enum makes the vocabulary a
  reviewed, append-only artifact with one definition site.
- **Per-runtime contracts** (each service publishes its own schemas) —
  rejected: N runtimes × M consumers of bespoke glue is exactly the coupling
  ADR-0003 exists to prevent; the gateway would import runtime packages,
  inverting the dependency direction.
- **Schemas living in `apps/api`** (gateway exports, runtimes import) —
  rejected: makes every runtime depend on the gateway application and its
  dependency tree (FastAPI, SQLAlchemy); the language must sit below both
  speakers, owned by neither.
- **An IDL (protobuf/OpenAPI) as the source of truth with generated code** —
  rejected for now: a second toolchain and a generation step to solve a
  problem pydantic already solves in a one-language monorepo. Revisit if a
  non-Python runtime appears — the contract's transport-free schema layer is
  precisely what would be transcribed into an IDL then.
- **Transport-aware contract** (HTTP status codes on errors, header
  constants, client/server helpers in the package) — rejected: the first
  gRPC or in-process runtime would fork the contract. Transport-free schemas
  are the reason a future `RuntimeClient` implementation swap costs zero
  gateway changes.
- **Strict readers (`extra="forbid"`)** — rejected: makes every additive
  field a lockstep deploy across gateway and all runtimes, which is how
  contracts ossify. Tolerance + append-only discipline is how protobuf
  survived decades.
- **One generic request/response schema for all capabilities** (`inputs:
  dict`, `outputs: dict`) — rejected: tensor-flavored genericity pushes
  validation to both ends and turns the contract into stringly-typed mush;
  capability-shaped schemas are the platform's admission test made concrete.

## Trade-offs

- **A shared package is a shared blast radius**: a bad contract release can
  affect every service. Mitigated by the package's near-zero logic, full
  strict typing, and golden-value tests that fail on any identifier drift.
- **Tolerant reading can mask a misspelled optional field** (it is silently
  ignored rather than rejected). Accepted: tests pin schemas, and the
  alternative (lockstep deploys) is worse.
- **Append-only vocabulary accumulates**: a deprecated capability's enum
  member never disappears. Accepted: deprecation is a registry/routing
  concern, not a vocabulary one.
- Cross-language runtimes get no contract enforcement until an IDL is
  introduced. Accepted until such a runtime is real.

## Consequences

- Platform-wide rule, CI-enforceable: **no string literal may name a
  capability**; everything imports `Capability`.
- The gateway's `RuntimeClient` and every runtime's API layer are both
  *implementations of this specification*; either can be rewritten without
  the other noticing.
- The evaluation package measures runtimes in the same vocabulary the
  gateway routes by (its M2 step 0 local `Literal` is replaced by this
  enum).
- ADR-0003's `/invoke`-endpoint sketch is superseded in detail by this ADR
  and the M2 service design: transport shape belongs to services, not the
  contract.
- New capabilities have a fixed, boring recipe: add enum member + schemas +
  tests in one additive change; gateway and runtime adopt on their own
  schedules.

## Future review criteria

- **M8 streaming** is the first structural stress: if streaming needs
  incremental result framing, design contract v2's streaming envelopes here
  — if that proves impossible transport-free, revisit this ADR.
- A **non-Python runtime** justifies revisiting the IDL alternative.
- If `CONTRACT_VERSION` needs more than one bump in a year, the evolution
  rules are failing — reopen.
- If `RuntimeMetadata` gains a field that is not purely operational, this
  ADR was violated, not outgrown — reject the change or supersede the ADR
  explicitly.
