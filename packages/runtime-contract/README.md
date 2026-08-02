# intelliai-runtime-contract

The permanent language spoken between the API gateway and every AI runtime.
Decision record: [ADR-0016](../../docs/adr/0016-runtime-contract-language.md).

## Module charter

**1. Why does this module exist?**
So that the gateway and N runtimes can evolve independently while speaking
one language. This package is closer to an API specification than to
application code: it defines *what is said* between planes — never how it
travels, who says it, or what happens when it is heard. It must survive
multiple generations of foundation models, runtime implementations,
transport protocols, and deployment strategies.

**2. What does it own?**
The shared vocabulary and schemas, and nothing else: the frozen `Capability`
enum (the platform's single source of truth for capability identifiers),
`CONTRACT_VERSION`, `RuntimeMetadata` (operational identity only),
success/error envelopes (`RuntimeResponse`, `RuntimeErrorResponse`), the
runtime failure taxonomy (`RuntimeErrorType`), usage vocabulary
(`UsageUnit`, `Usage`), timing (`RuntimeTiming`), and per-capability schemas
(today: `transcription`).

**3. What must it never own?**
Networking, HTTP, transport bindings, serialization decisions outside the
schema layer, logging, retries, timeouts, authentication, routing, billing,
engine or model references, business logic, inference logic. Its dependency
list is pydantic — permanently. FastAPI, SQLAlchemy, Torch, Whisper, or any
runtime library appearing in this package is a boundary violation, not a
convenience.

**4. Who may import it?**
Everyone: the gateway (`apps/api`), every runtime service (`services/*`),
the evaluation package (`ml/evaluation`), and future SDK/tooling. It sits at
the bottom of the dependency graph, owned by neither speaker.

**5. What may it import?**
The standard library and pydantic. Nothing else, ever.

**6. How do future capabilities extend it?**
By one additive change: append a `Capability` member (never rename, remove,
or reuse), add a `<capability>.py` schema module beside `transcription.py`,
add any new `UsageUnit` members the capability bills in, and pin all of it
with golden tests. Members land with their schemas, not speculatively.
Within a contract version all changes are additive-with-defaults; breaking
changes increment `CONTRACT_VERSION` — a rare, platform-wide event
(ADR-0016 evolution rules).

## Design rules that hold everywhere in this package

- **Models are frozen** — a validated message is immutable.
- **Models are tolerant readers** — unknown fields are ignored, so gateway
  and runtimes upgrade on independent schedules, and undeclared fields are
  useless to send (the anti-dumping-ground property, ADR-0016).
- **No string literals for vocabulary** — capabilities, error types, and
  usage units are enums; every identifier has exactly one definition site.
- **Errors are transport-free** — `RuntimeErrorType` knows no HTTP status
  codes and dictates no retry policy; translating to the public error
  envelope (ADR-0009) is the gateway's job alone.

## Ownership boundaries (summary — normative text in ADR-0016)

Gateway: auth, authz, tenancy, routing, retries, end-to-end timeout,
OpenAI compatibility, billing, request accounting.
Runtime: preprocessing, model execution, postprocessing, inference metadata.
The runtime never sees an API key or an organization; the gateway never
sees an engine or a model file.
