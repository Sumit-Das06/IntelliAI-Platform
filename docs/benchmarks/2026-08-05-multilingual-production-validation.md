# Multilingual production validation — M5 step 7

**What this validates.** The whole multilingual path on the **shipped
catalog**, with both real engines, over real sockets. No overrides
anywhere: the gateway ran `default_registry()`, the STT runtime hosted
real whisper-small weights, and the TTS runtime hosted real kokoro-82m.

- **Date:** 2026-08-05 · **Host:** Intel Core i7-14650HX, Windows 11,
  native processes against the compose Postgres and Redis
- **Topology:** gateway `:18000` → `stt-runtime` `:18001`
  (whisper-small, cpu-int8) and `tts-runtime` `:18002` (kokoro-82m)

## 1. Two defects found, both fixed

Production validation exists to find what tests with fakes cannot. It
found two, in the same request.

**A regional tag reached the engine and became a 500.** `hi-IN` routed
correctly to the `hi` route, and the gateway then forwarded the *raw*
tag to the runtime. faster-whisper accepts base subtags only, raised
`ValueError('hi-IN' is not a valid language code)`, and the customer got
`internal_error`.

The normalization law was being applied at the routing boundary and
nowhere else. Fixed at the source: **the engine is told what routing
decided, never what the customer typed.** `hi-IN` is a fact about the
request, not a language any engine has — the three-language distinction
(§4.2) made visible by a 500.

**The adapter let a library exception escape.** Even with the first fix,
any language the engine does not accept would have produced a 500 rather
than a 400. An adapter's job is contract-shaped params in, contract-shaped
results out — *including when the engine says no*. The whisper adapter now
translates a rejected language into `INVALID_INPUT` with `param=language`.

Both are covered by regression tests. One of those tests replaced an
assertion that had encoded the defect: the Step 3 suite asserted the full
tag reaches the runtime, which is exactly what broke here.

## 2. The shipped path, both capabilities

After the fixes, on the shipped catalog:

| Capability | Declared | Status | Latency | Result |
|---|---|---|---|---|
| transcription | `en` | 200 | 1429 ms | transcribed |
| transcription | `hi` | 200 | **30184 ms** | empty transcript, no hallucination |
| transcription | `hi-IN` | 200 | **27224 ms** | routed as `hi`, recorded as `hi` |
| transcription | `ar` | 200 | 1529 ms | **hallucinated text on non-speech** |
| transcription | *(undeclared)* | 200 | 2877 ms | default route |
| speech_synthesis | `reference-alto` | 200 | 912 ms | 85 244 bytes of audio |
| speech_synthesis | `reference-bass` | 200 | 1069 ms | 94 844 bytes |
| speech_synthesis | *(default voice)* | 200 | 993 ms | 85 244 bytes |

### Two honest findings, recorded without diagnosis

**Hindi costs an order of magnitude more.** 30.2 s versus 1.4 s for
English on the same one-second clip — RTF ≈ 30 on the shipped path. Step
4 measured the same effect at the runtime level (~9× on a 5-second clip);
at production scale on short audio it is worse. **The Hindi route's
latency profile is not the English route's**, and capacity planning that
assumed otherwise was wrong.

**Arabic hallucinates on non-speech.** The clip is a 440 Hz tone. English
and Hindi return nothing; Arabic returns `اشتركوا في القناة` — "subscribe
to the channel", a caption artefact from the training data. This is
exactly what the `available` rung exists to collect: Arabic is served,
labelled, and promised nothing, and now there is a measured reason why.

Neither is diagnosed here. The numbers stand either way.

## 3. The ledger, both capabilities

```
transcription     lang=en   artifact=whisper-small  deployment=stt-runtime  audio_seconds=1.0
transcription     lang=hi   artifact=whisper-small  deployment=stt-runtime  audio_seconds=1.0
transcription     lang=hi   artifact=whisper-small  deployment=stt-runtime  audio_seconds=1.0
transcription     lang=ar   artifact=whisper-small  deployment=stt-runtime  audio_seconds=1.0
transcription     lang=en   artifact=whisper-small  deployment=stt-runtime  audio_seconds=1.0
speech_synthesis  lang=en   artifact=kokoro-82m     deployment=tts-runtime  characters=21, audio_seconds=1.775
speech_synthesis  lang=en   artifact=kokoro-82m     deployment=tts-runtime  characters=21, audio_seconds=1.975
speech_synthesis  lang=en   artifact=kokoro-82m     deployment=tts-runtime  characters=21, audio_seconds=1.775
```

**M4's TTS-language gap is closed in production.** Synthesis events carry
`language=en`, derived from the voice that rendered them — with no public
language field anywhere (F-M5-7). Every row carries the artifact and the
deployment that served it.

## 4. Commercial plane

Scoped to the validation organization:

```
RECONCILIATION (2026-08) : CLEAN
LADDER COVERAGE          : 0 contradictions
   transcription     en  supported     2 request(s)
   transcription     hi  available     2 request(s)
   transcription     ar  available     1 request(s)
   speech_synthesis  en  supported     3 request(s)
   speech_synthesis  hi  unavailable   0 request(s)
   speech_synthesis  ar  unavailable   0 request(s)
```

**Per-route commercial fingerprint — identical across all three routes:**

```
en / hi / ar → capability=transcription  public_model=intelliai-stt
               billable=true  origin=customer  units=[audio_seconds]
               price_book=internal-2026-08-v1  algorithm=1
               artifacts=[whisper-small]
```

Routing changed which language was served; nothing commercial moved. The
Commercial Identity Invariant holds per route, in production, on real
traffic.

## 5. A finding about the check itself

Run **unscoped**, the new ladder-coverage check reports ~2 000
`speech_synthesis` requests each for `hi` and `ar` — languages the ladder
refuses — and calls them serving defects.

They are not. They are dev-database residue: fixtures written with
`origin=customer` and timestamps dated 2026-08-15, from a period when
synthesis carried a `language` parameter that no longer exists. No
policy-window rule can distinguish them from real traffic, because their
timestamps are fabricated.

Two things follow, and neither is "soften the check":

- **The check is correct and stays.** Serving a language we say we refuse
  must not scroll past, and this is the second time an unscoped read of
  the dev database has produced a confident wrong answer (M4 review,
  same lesson).
- **Test fixtures must not write `origin=customer`.** The origin taxonomy
  exists precisely so internal traffic is metered and never mistaken for
  a customer's. Registered as debt with a second consumer.

## 6. What was not validated

- **Hindi as a promotable route.** It cannot be, and that is the design
  working: no Hindi speech corpus exists (F-M5-8), so no Hindi run can be
  a quality claim and the enablement bar returns `BLOCKED`.
- **A second real engine per capability.** The shipped catalog routes all
  three languages to one artifact. Multi-artifact routing is proven with
  simulated artifacts (Steps 3 and 6) because adopting a second engine is
  Research Framework territory, not M5's.
- **Throughput under multilingual load.** The M4 commercial baseline
  (+18 ms p50) is unchanged by routing — one dictionary lookup — and a
  load measurement per language belongs with a real per-language engine.
