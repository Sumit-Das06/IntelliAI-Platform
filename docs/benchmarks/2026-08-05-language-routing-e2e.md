# Language-routed serving, end to end — M5 step 3

**What this records.** One public model resolved to two different
artifacts, per request, from registry state — across three real processes
with real TCP between every hop. The automated suite proves the same
behaviour in CI with fake runtimes; this exists because "the gateway
routes" and "the gateway routes over a socket to a second deployment"
are different claims, and only one of them was previously evidenced.

- **Date:** 2026-08-05 · **Host:** Intel Core i7-14650HX, Windows 11,
  native gateway and runtime processes against the compose Postgres and
  Redis
- **Topology:**

```
   customer (httpx)
        │  HTTP :18000
        ▼
   gateway  ──── resolve("intelliai-stt", language=…) ──► registry
        │
        ├─ deployment "stt-runtime"        HTTP :18001   hosts  reference
        └─ deployment "stt-runtime-indic"  HTTP :18002   hosts  future-hi-v1
```

Both runtimes are step 2 multi-slot processes; the second hosts a
simulated future artifact, so no model weights are involved anywhere.
The catalog is a `ServingRoute` set: `en → reference` (supported, with
evidence), `hi → future-hi-v1` (available, on the second deployment),
`ar → unavailable`.

## 1. Routing

| Declared | Status | Latency | Served by | Deployment |
|---|---|---|---|---|
| `en` | 200 | 102.1 ms | `reference` | `stt-runtime` (:18001) |
| `hi` | 200 | 88.1 ms | `future-hi-v1` | `stt-runtime-indic` (:18002) |
| `hi-IN` | 200 | 96.3 ms | `future-hi-v1` | `stt-runtime-indic` (:18002) |
| *(undeclared)* | 200 | 98.1 ms | `reference` | `stt-runtime` (:18001) — the default route |
| `ar` | **400** | **19.2 ms** | — | refused before any plane was crossed |

Confirmed from both ends. The runtimes' own logs show runtime A served
only `reference` and runtime B served only `future-hi-v1` — four
completions each across two runs — so the split is not inferred from the
gateway's account of itself.

The refusal is ~5× faster than a served request because it does no work:
no runtime call, no inference, no ledger write. That latency gap is the
measurement of "refused before crossing a plane".

## 2. The refusal, as customers see it

```
400  {"error": {"code": "language_not_supported", "param": "language",
      "message": "The model 'intelliai-stt' does not serve the language 'ar'.
                  Languages served: en, hi."}}
```

It names what *is* served, so the answer is actionable, and it names
nothing else — no artifact, no deployment, no engine.

## 3. Demand evidence

Every refusal emitted one structured event:

```
language.refused  capability=transcription  model=intelliai-stt  language=ar
                  served_languages=['en','hi']  organization_id=org_…
                  request_id=req_…
```

This is the only record that will ever exist of someone asking for a
language we do not serve. It produces **no** billable event — a refusal
runs no inference and costs the customer nothing — and it carries the
request id, so it joins to the request that provoked it. Persisting these
as request events is M4's registered debt; this is now its second caller.

## 4. Ledger facts

Org-scoped read of `usage_events` after the run:

| `public_model_id` | `language` | `lineage.artifact` | billable | `audio_seconds` |
|---|---|---|---|---|
| `intelliai-stt` | `en` | `reference` | true | 1.000000 |
| `intelliai-stt` | `hi` | `future-hi-v1` | true | 1.000000 |
| `intelliai-stt` | `hi-IN` | `future-hi-v1` | true | 1.000000 |
| `intelliai-stt` | `und` | `reference` | true | 1.000000 |

Four things are visible here and each is a law:

- **The public model never changes.** The customer bought
  `intelliai-stt`; which artifact answered lives in lineage, internal
  forever (Commercial Identity Invariant).
- **`hi-IN` is recorded in full and routed as `hi`.** Normalization is a
  routing concern; the ledger stores the fact as declared.
- **`und` is the undeclared request**, recorded as the engine observed
  it — the ledger stores what happened, not what was asked for.
- **The refusal produced no row at all.** Four requests served, four
  rows; the fifth request is in the event stream and not in the ledger.

The read was org-scoped deliberately. An unscoped query over this
database returns residue from every past measurement — the M4 lesson,
and the first unscoped attempt at this table reproduced it exactly.

## 5. What was not measured

- **Throughput or overhead under load.** Routing adds one dictionary
  lookup to resolution; the commercial-plane baseline (+18 ms p50)
  remains the platform's overhead measurement and is untouched by this
  step. A load measurement belongs to step 7.
- **The deployment → URL configuration surface.** The gateway's client
  map was constructed directly for this demonstration. Making that a
  deployment-keyed configuration is step 6's scope, deliberately not
  built here.
- **Real foundation models.** By design: routing is proven by the
  architecture, not by the models. Step 7 runs the same path with the
  incumbent serving a real, promoted Hindi route.
