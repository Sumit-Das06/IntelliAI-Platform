# STT Runtime — Production Profile (14B)

> The facts an operator needs about the inference service, read from the
> implementation (`services/stt-runtime/src/intelliai_stt_runtime/`).
> This document selects nothing new: the current runtime **is** the
> production engine (ADR-0015/0016; no fine-tuning, no GPU, no new
> model in this milestone).

## Model configuration

- Slots are deployment configuration: `INTELLIAI_STT_SLOTS=whisper` in
  production (pinned explicitly by the prod overlay — never inherited).
  The first slot serves requests that pin no artifact.
- The artifact is **hash-pinned**; first boot downloads ~480 MB into the
  `modelcache` volume and every boot re-verifies. A failed hash check is
  a refusal to serve, not a warning.
- Precision is configuration, never identity: `int8` compute
  (`INTELLIAI_STT_WHISPER_COMPUTE_TYPE`), CPU-only by design (ADR-0015 —
  CPU-first, GPU-ready later).
- The removed `DEFAULT_ENGINE` setting is a **tripwire**: if it is set,
  startup aborts loudly rather than silently serving the wrong engine.

## Startup and failure behavior

- Compose healthcheck probes the runtime's own `/health/ready`;
  `start_period: 600s` covers the first-boot download. Ready means
  "model loaded and warm".
- The gateway now mirrors this in its own readiness roster
  (`stt-runtime` check): runtime down → gateway reports **degraded**
  (HTTP 200, control plane serves, monitors alarm on the keyword).
- Runtime failures reach customers only as the public taxonomy
  (`service_unavailable_error` family with `Retry-After`); engine names
  never cross the boundary.

## Concurrency and capacity

- `max_concurrency = 2` inference slots (thread pool) and
  `max_queue = 8` waiting requests. Beyond both, the runtime answers
  **`overloaded` immediately** — a fast honest no; the gateway/client
  own retries. Raise the knobs only with measurements on the actual VPS
  (docs/benchmarks/ holds the ladder methodology).
- The gateway's end-to-end deadline is 120 s
  (`INTELLIAI_RUNTIMES_TIMEOUT_SECONDS`); the runtime owns per-stage
  limits under it (ADR-0016).

## Request limits (defense-in-depth stack)

| Layer | Limit |
| --- | --- |
| Caddy edge | 30 MB request body |
| Gateway | 30 MiB body ceiling at read time (`INTELLIAI_LIMITS_MAX_REQUEST_BYTES`) |
| Runtime | 25 MiB upload, 600 s audio, 30 s decode timeout (ffmpeg) |

The runtime's limits stay the customer-facing message for oversized
*audio*; the outer layers exist for memory pressure.

## Sizing guidance (pilot)

The deployment guide's VPS class (8 vCPU / 16 GB) is sized for this
runtime plus the full stack. The int8 CPU profile and the 2-slot
concurrency are the measured pilot configuration — the quality/latency
baseline is pinned in the registry catalog (`quality_baseline`), and any
resizing follows a bench run, not a guess. **Not verified from the
current implementation:** exact resident memory on the production VPS —
measure during the first deployment and record it here.
