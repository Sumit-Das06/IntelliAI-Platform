# Deployment topology: packed versus isolated — M5 step 6

**What this measures.** What it costs to run one capability as several
deployments instead of one — the number F-M5-5 (packing posture) needs,
and the demonstration that two deployments of one capability serve side
by side from configuration alone.

- **Date:** 2026-08-05 · **Host:** Intel Core i7-14650HX, Windows 11,
  native · **Method:** one fresh subprocess per configuration; resident
  set read immediately before the lifespan starts and immediately after
  readiness; slot figures are the runtime's own, read from `/info`.

## 1. The cost of isolation

| Topology | Process(es) | Startup | Slot init | RSS after load |
|---|---|---|---|---|
| whisper alone | 1 | 4534.6 ms | 4047.8 ms | **410.5 MiB** |
| a second artifact alone | 1 | 48.3 ms | 0.5 ms | **51.2 MiB** |
| **isolated** (both, separate processes) | 2 | (in parallel) | — | **461.7 MiB** |
| **packed** (both, one process) | 1 | 4409.3 ms | 3956.8 ms | **407.2 MiB** |

**Isolation costs ~54.5 MiB — one Python interpreter and its imports.**
Nothing else moves: the artifacts cost what they cost, and hosting them
apart adds a process rather than a model.

Read against the models, that is the whole argument. 54 MiB is **~13%**
on top of a whisper-small deployment and **~4%** of the 1.4 GiB the same
engine occupies under container measurement (M2/M3). Packing buys back
one interpreter; it spends a shared worker pool and a shared blast
radius — one engine's crash-loop taking down languages that were healthy,
and one artifact's load starving its neighbour through the admission
limit they share (ADR-0018).

**This supports the default posture, and it is not a ruling.** F-M5-5 is
still the founder's: the recommendation remains one artifact per
deployment on CPU, with packing justified per adoption by measured
residency headroom on the target hardware — a number this document does
not have, because it depends on the machine the deployment lands on.

## 2. Two deployments of one capability, side by side

Live, over real sockets, with the client map coming from
**configuration** — not from code:

```
INTELLIAI_RUNTIMES_STT_URL=http://127.0.0.1:18001          → deployment "stt-runtime"
INTELLIAI_RUNTIMES_DEPLOYMENTS=stt-runtime-indic=http://127.0.0.1:18002
```

| Declared | Status | Served by | Deployment |
|---|---|---|---|
| `en` | 200 | `reference` | `stt-runtime` |
| `hi` | 200 | `future-hi-v1` | `stt-runtime-indic` |
| `hi-IN` | 200 | `future-hi-v1` | `stt-runtime-indic` |
| *(undeclared)* | 200 | `reference` | `stt-runtime` |
| `ar` | 400 | — | refused before any plane was crossed |

Confirmed from both ends: each runtime's own log shows three completions
and only its own artifact. The ledger's internal lineage now names the
deployment that answered:

```
intelliai-stt  en      artifact=reference      deployment=stt-runtime
intelliai-stt  hi      artifact=future-hi-v1   deployment=stt-runtime-indic
intelliai-stt  hi-IN   artifact=future-hi-v1   deployment=stt-runtime-indic
intelliai-stt  und     artifact=reference      deployment=stt-runtime
```

That is what makes cost-to-serve attributable once a capability has more
than one deployment — capacity and residency are deployment properties.

## 3. Deployment isolation, demonstrated by breaking one

With `stt-runtime-indic` killed and nothing else changed:

| Declared | Status | |
|---|---|---|
| `en` | **200** | the default deployment keeps serving |
| `hi` | **503** | `runtime_unavailable`, for that route only |

Partial multilingual availability is honest by construction: a down
deployment 503s its own routes while the others serve. There is no
cross-artifact fallback and there must not be — an automatic quality
substitution is a promotion nobody approved, and fallback is a Serving
Strategy that does not exist (ADR-0025 decision 5).

## 4. What was not measured

- **Throughput under multi-deployment load.** Capacity is a deployment
  property and each deployment's pool is unchanged; a packing decision
  would need a throughput measurement under contention, which is the
  measurement F-M5-5 should ask for on real target hardware.
- **Residency headroom on production hardware.** The only number that
  can justify packing, and it is a property of the machine, not of this
  laptop.
- **Two real engines packed together.** The synthesis extra pulls a
  multi-gigabyte install this measurement did not need: §1 establishes
  the machinery cost, and each engine's residency is already measured in
  M2/M3. Their sum is the packed figure.
