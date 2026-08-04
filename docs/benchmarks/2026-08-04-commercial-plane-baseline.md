# Commercial Plane — Production Baseline v1

- **Date:** 2026-08-04
- **Platform version:** 0.4.0 (Milestone 4, step 7)
- **Status:** permanent baseline — the reference every later commercial
  change is compared against
- **Scope:** metering, admission control, entitlement, pricing, rollups,
  reconciliation. Speech quality and inference performance have their own
  baselines under `ml/evaluation/{stt,tts}/`.

> **Where platform baselines live.** Capability baselines (what a model
> does, how fast) belong beside the capability, in `ml/evaluation`.
> Plane-level baselines (what the platform costs to operate, whether its
> books balance) belong here. The two answer different questions and are
> replaced on different schedules.

## 1. Environment

| | |
|---|---|
| Host | Windows 11, Docker Desktop |
| Gateway | `intelliai-api` container, image rebuilt at M4 step 7 |
| Runtimes | `tts-runtime` (Kokoro-82M, CPU), `stt-runtime` (whisper-small, CPU) |
| Postgres | 16-alpine, `pool_size=20`, `pool_max_overflow=10` |
| Redis | 7-alpine, limiter socket budget 250 ms, breaker 3 failures / 5 s |
| Price book | `internal-2026-08-v1` (internal only, F3) |
| Rating algorithm | v1 |

**Numbers from this machine are a floor, not a forecast.** Docker
Desktop on Windows adds measurable network cost to every Postgres and
Redis round trip; a Linux deployment will do better. They are recorded
so that a future change can be compared against them on the same
hardware.

## 2. Commercial overhead on a served request

Measured by removing one layer at a time from the real gateway, against
real Postgres and real Redis, with inference held constant by a fake
runtime — the question is the cost of the *commercial* path, and a real
engine's variance would drown it.

### 2.1 At realistic TTS latency (800 ms inference, 20 requests)

| Configuration | p50 | p95 | Δ p50 |
|---|---|---|---|
| bare (no commercial plane) | 829.32 ms | 838.48 ms | — |
| + metering (ledger write) | 841.73 ms | 855.05 ms | +12.41 ms |
| + entitlement (quota, spend) | 839.70 ms | 846.35 ms | −2.03 ms¹ |
| + admission (rate, concurrency) | 847.26 ms | 855.29 ms | +7.56 ms |

**Commercial plane total: +17.94 ms p50 — 2.1% of a served request.**

¹ Negative because it is inside run-to-run noise at this scale; the
isolated cost of the quota aggregate is 1–3 ms (§2.3).

### 2.2 At small inference (50 ms, 60 requests) — attribution

The same layers, measured where they are resolvable rather than lost in
noise:

| Configuration | p50 | Δ p50 |
|---|---|---|
| bare | 78.03 ms | — |
| + metering | 89.12 ms | **+11.09 ms** |
| + entitlement | 89.95 ms | **+0.83 ms** |
| + admission | 96.28 ms | **+6.33 ms** |

**Total +18.25 ms.** The absolute overhead is stable at ~18 ms
regardless of inference duration, which is the number to carry forward —
the *percentage* is entirely a function of the denominator chosen.

Against M3's measured single-sentence TTS latency (814 ms), the
commercial plane costs **~2.2%**. The M3 gateway overhead was 2.0%; the
whole commercial plane roughly doubles the gateway's share of a request
while remaining a rounding error against inference.

### 2.3 Component costs, isolated

| Operation | Cost | Notes |
|---|---|---|
| Quota aggregate, 100 events in period | 1.31 ms | grouped SUM over one indexed range |
| Quota aggregate, 1 000 events | 2.58 ms | |
| Quota aggregate, 5 000 events | 8.36 ms | ~1.6 ms per 1 000 events |
| Rollup read, any size | **0.86–0.94 ms** | constant time |
| Rollup rebuild, 5 000 events | 14.89 ms | |
| Rollup rebuild, 20 000 events | 30.76 ms | |
| Rating 1 000 events | 2.30 ms | 200 repetitions → 1 distinct result |
| Rating 5 000 events | 12.49 ms | 50 repetitions → 1 distinct result |

**Rollup speed-up over the ledger aggregate: 7.4× at 5 000 events,
25.9× at 20 000.** The cache read is constant time while the truth grows
linearly.

## 3. Database concurrency (R2, resolved)

Founder decision F8 raised `pool_size` from 5 to 20 rather than
weakening the durability guarantee that transaction ownership provides.

| Concurrency | Pool checked out (before → after) | Peak concurrent in runtime (before → after) | p50 (before → after) |
|---|---|---|---|
| 25 | 15 → **25** | 15 → **25** | — |
| 40 | 15 → **30** | 15 → **30** | 1248 → **1161 ms** |

The ceiling moved to exactly `pool_size + overflow = 30`. The next
ceiling is Postgres `max_connections`, not this design.

## 4. End-to-end production flow

Against the running container, over real HTTP, with real Kokoro audio.

```
GET  /v1/models                -> 200   (no engine name in the response)
POST /v1/audio/speech          -> 200   135,644 bytes   x-ratelimit-remaining=118
POST /v1/audio/speech          -> 200   135,644 bytes   (Idempotency-Key set)
POST /v1/audio/speech          -> 200   135,644 bytes   (same Idempotency-Key)
POST /v1/audio/transcriptions  -> 200

ledger events for this tenant : 3
  speech_synthesis  intelliai-tts  billable=True  {characters: 37, audio_seconds: 2.825}
  speech_synthesis  intelliai-tts  billable=True  {characters: 37, audio_seconds: 2.825}   idem=m4-prod-idem
  transcription     intelliai-stt  lang=en        {audio_seconds: 11}
rollup rebuilt                : {audio_seconds: 16.65, characters: 74}
rated                         : 0.00 USD  (books=('internal-2026-08-v1',), algo=v1)
  unrounded                   : 0.002775
reconciliation                : CLEAN
```

**Three synthesis requests produced two ledger events.** The second and
third carried the same `Idempotency-Key`; exactly one was billed. That is
at-most-once billing demonstrated in production, not in a unit test.

**The rounding rule is visible here too:** $0.002775 rounds to $0.00 at
the line. A line worth less than half a cent rounds to zero, by design —
we do not charge fractions of a cent.

## 5. Recovery under infrastructure failure

### 5.1 Redis stopped mid-operation

```
docker compose stop redis

GET  /v1/models                -> 200
POST /v1/audio/speech          -> 200   135,644 bytes   headers: {}   ← nothing published
POST /v1/audio/speech          -> 200   135,644 bytes   headers: {}
POST /v1/audio/speech          -> 200   135,644 bytes   headers: {}
POST /v1/audio/transcriptions  -> 200
ledger events for this tenant : 2      ← idempotency STILL enforced
reconciliation                : CLEAN
```

Three things happened at once, and all three are the design working:

1. **The platform kept serving.** Protection degraded; availability did
   not (ADR-0022).
2. **No rate-limit headers were published.** The Operational Honesty
   Principle in production: when nothing was measured, nothing is
   claimed. Silence, not a plausible number.
3. **Idempotency still held** — it lives in a database constraint, not
   in Redis, so the guarantee that protects a customer's invoice survives
   the loss of the component that protects our capacity.

Alarms observed in the container: `ratelimit.circuit_opened` ×1,
`ratelimit.concurrency_unavailable` ×1 — one per trip, not one per
request.

### 5.2 Redis restored

```
docker compose start redis
POST /v1/audio/speech -> 200   x-ratelimit-remaining=118 ...
reconciliation                : CLEAN
```

The breaker closed and headers returned without intervention.

### 5.3 Cache corruption

Exercised in the suite rather than in production: a rollup is corrupted,
reconciliation reports `rollup_disagrees_with_ledger`, a rebuild repairs
it, and the same audit then reports clean. The ledger is byte-identical
throughout — verified by comparing event ids and quantities before and
after.

## 6. Reconciliation and analytics

`intelliai commercial-report [--month YYYY-MM]` walks the chain and
**exits non-zero if anything disagrees** — it is built to be scheduled,
and a reconciliation whose failure nobody notices is the silent revenue
loss §6.1 forbids.

Checks performed:

| Link | Check | Severity |
|---|---|---|
| gateway → ledger | fallback sink is empty | critical |
| ledger | billable events carry a measurement | critical |
| ledger | non-compensating events carry a request id | critical |
| ledger | reversals state a reason | critical |
| ledger | no zero quantities | critical |
| rollups | cache agrees with the ledger | critical |
| rollups | cache exists for the period | warning |
| rating | ledger and rollup rate to the same money | critical |

Anomaly queries: usage spikes against the tenant's **own** 7-day
baseline, failure-rate share, stale rollups, reversal activity.

## 7. Language analytics (Core Speech Language Policy)

The report groups usage by language and capability, counts adoption as
**distinct organizations** rather than requests, and separates policy
languages from unserved demand.

```
LANGUAGE ADOPTION (Core Speech Language Policy)
  en : 3 organization(s)
  hi : 3 organization(s)
  ar : 3 organization(s)
  outside the policy : none
```

**Known gap, found by this validation.** The production flow recorded
`language=en` for transcription and `language=None` for synthesis,
because the public TTS API has no `language` parameter — M4 preserved
public APIs unchanged, deliberately. Language analytics are therefore
**complete for STT and blank for TTS** until the public synthesis
surface accepts a language. Registered as platform work; it is a product
decision (does a customer state a language, or is it inferred from the
voice?) rather than a metering one.

## 8. What this baseline commits us to

Numbers a future change must beat, or explain:

| Property | Baseline | Source |
|---|---|---|
| Commercial overhead per request | **+18 ms p50** (~2.1%) | §2 |
| Quota aggregate at 5 000 events | 8.36 ms | §2.3 |
| Rollup read | constant, <1 ms | §2.3 |
| Rating reproducibility | 1 distinct result over 250 repetitions | §2.3 |
| Request concurrency ceiling | 30 (pool + overflow) | §3 |
| Redis-down customer impact | none, beyond absent headers | §5.1 |
| Reconciliation on real traffic | CLEAN | §4 |

## 9. Known limitations, stated rather than implied

1. **The gateway → ledger link is only partially reconciled.** Comparing
   successful billable responses to billable ledger rows needs *persisted*
   request events; M4 records requests as structured logs only. What is
   proven today is that nothing was *rejected* (the fallback sink is
   empty). Persisting request events completes the link — M4 debt.
2. **TTS language is unrecorded** (§7).
3. **Quota reads the ledger, not the rollup.** Correct by choice at
   present volumes; the graduation trigger is ~25 000 events in one
   tenant's month, where the aggregate reaches ~40 ms.
4. **Rating from a rollup assumes one price book covers the period.** A
   period spanning a price change must rate from the ledger; the rollup
   has already discarded the timestamps book selection needs.
5. **Measurements are from Docker Desktop on Windows.** A floor, not a
   forecast.
