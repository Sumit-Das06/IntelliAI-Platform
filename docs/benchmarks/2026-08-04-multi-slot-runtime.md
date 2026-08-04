# Multi-slot runtime measurements — M5 step 2

**What this measures.** The cost of the multi-slot *machinery*, isolated
from the cost of the models it hosts. Step 2 made one runtime process
able to host N artifacts; the question this answers is what that
capability costs when the artifacts themselves cost nothing, and what it
costs on top of a real foundation model.

- **Date:** 2026-08-04 · **Host:** Intel Core i7-14650HX, Windows 11,
  native (the same machine as the M2/M3 baselines)
- **Method:** one fresh subprocess per configuration, so imports are not
  shared between runs. Resident set read from the Windows process API
  immediately before the lifespan starts (app object built, no engines
  loaded) and immediately after readiness. Slot load/warm-up figures are
  the runtime's own measurements, read from `/info`. Endpoint latency is
  the median of 30 in-process calls.
- **Simulated artifacts** are the deterministic reference engine hosted
  under other identities (`reference:fake-a`) — weight-free by
  construction, which is exactly why they isolate the machinery.

## 1. Machinery cost — weight-free artifacts

### Transcription (`stt-runtime`)

| Hosted artifacts | Startup | RSS before → after | Δ RSS | `/health/ready` | `/info` |
|---|---|---|---|---|---|
| 1 | 31.2 ms | 49.0 → 50.2 MiB | 1.23 MiB | 0.514 ms | 0.565 ms |
| 2 | 45.7 ms | 49.0 → 50.2 MiB | 1.20 MiB | 0.552 ms | 0.597 ms |
| 4 | 33.4 ms | 49.0 → 50.2 MiB | 1.14 MiB | 0.529 ms | 0.546 ms |
| 8 | 30.6 ms | 49.2 → 50.3 MiB | 1.11 MiB | 0.491 ms | 0.543 ms |

### Synthesis (`tts-runtime`)

| Hosted artifacts | Startup | Σ slot init | RSS before → after | Δ RSS | `/health/ready` | `/info` |
|---|---|---|---|---|---|---|
| 1 | 7.0 ms | 2.4 ms | 49.1 → 50.1 MiB | 0.97 MiB | 0.493 ms | 0.505 ms |
| 2 | 9.6 ms | 4.8 ms | 49.2 → 50.2 MiB | 1.02 MiB | 0.506 ms | 0.509 ms |
| 4 | 32.2 ms | 20.7 ms | 48.8 → 49.7 MiB | 0.94 MiB | 0.567 ms | 0.537 ms |
| 8 | 22.6 ms | 18.0 ms | 48.7 → 49.7 MiB | 0.97 MiB | 0.515 ms | 0.561 ms |

**Reading these.** Resident memory is flat across 1→8 hosted artifacts:
the per-slot bookkeeping is two dictionary entries and a frozen record,
and it does not appear above measurement noise. `/health/ready` and
`/info` are likewise flat — readiness is one boolean regardless of slot
count, and `/info` builds a list whose length is the only thing that
grows. Startup varies more than it scales; on synthesis, where the
warm-up probe performs a real (if tiny) inference per slot, slot
initialisation is the visible term at roughly 1.2 ms per additional
slot, and it is strictly sequential by design — every slot is warm
before the process reports ready.

**The conclusion that matters:** hosting more artifacts costs what the
artifacts cost, and essentially nothing else. Residency is a property of
the models, not of the mechanism.

## 2. Real-model cost — Whisper plus a simulated future artifact

One process, `INTELLIAI_STT_SLOTS=whisper,reference:future-hi-v1`:

| Configuration | Startup | Δ RSS | whisper load / warm-up | second slot load / warm-up |
|---|---|---|---|---|
| `whisper` alone | 3555.0 ms | 357.88 MiB | 1098.7 / 2032.6 ms | — |
| `whisper` + simulated artifact | 3267.8 ms | 356.95 MiB | 958.8 / 1898.7 ms | 0.1 / 0.1 ms |

Adding a second hosted artifact to a real deployment cost **0.2 ms of
startup and no measurable memory**. The startup difference between the
two rows is Whisper's own load and warm-up variance, not the slot.

The M2/M3 residency figures stand unchanged as the additive term:
whisper-small ≈ 1.4 GiB and kokoro-82m ≈ 2.0 GiB resident under
container measurement. Two *real* engines in one process therefore cost
the sum of their residencies — which is precisely why ADR-0026 keeps
one-artifact-per-deployment as the default posture on CPU and makes
packing a per-adoption decision backed by measured headroom (F-M5-5).
This document measures the mechanism; it does not argue for packing.

## 3. Serving proof

Same process, real weights and a simulated artifact side by side:

```
/info
   slot=default        artifact=whisper-small  load=957.6ms  warmup=1912.5ms
   slot=future-hi-v1   artifact=future-hi-v1   load=0.4ms    warmup=0.2ms
   ready: {"status": "ready"}

pinned whisper-small -> 200  served_by=whisper-small  "And so my fellow Americans, ask not
                             what your country can do for you."   inference 2141.9 ms
pinned future-hi-v1  -> 200  served_by=future-hi-v1   "reference transcription of 11.00
                             seconds [a29462b8ebd4]"              inference 0.2 ms
unpinned             -> 200  served_by=whisper-small  (the `default` slot's role)
pinned future-ar-v1  -> 400  invalid_input, param=model  (not hosted here)
```

Clip: `jfk-wav` (11.0 s, `stt-eval-seed@v1`). The transcript matches the
M2 baseline for this clip, so hosting a second artifact changed nothing
about what the first one produces.

## 4. What was not measured

- **Two real engines in one process.** The synthesis engine's extra
  pulls a multi-gigabyte install that this measurement did not require:
  the machinery cost is established by §1 and §2, and the residency of
  each real engine is already measured in M2/M3. When packing is
  actually proposed (F-M5-5), the measurement it needs is residency
  headroom on target hardware, not this one.
- **Throughput under multi-slot load.** Capacity is a deployment
  property: artifacts sharing a deployment share its worker pool
  (ADR-0018, ADR-0026), and that pool is unchanged by this step. A
  packing decision would need a throughput measurement; hosting alone
  does not.
- **Cold start with two downloading artifacts.** Both would download
  and verify sequentially before readiness. The download cost is the
  artifacts', already measured per artifact in M2/M3.
