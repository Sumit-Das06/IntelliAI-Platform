# First multilingual STT baselines — M5 step 4

**These are the platform's first language-sliced evaluation records.** Each
names the promise it measured, the language slice, the artifact and
version that served, the build, the deployment that answered, and the
corpus version — so each is reproducible from records alone, years from
now, with nothing remembered by a person.

- **Date:** 2026-08-05 · **Host:** Intel Core i7-14650HX, Windows 11,
  native · **Artifact:** whisper-small v1, `cpu-int8` build ·
  **Engine:** faster-whisper 1.2.1 · **Corpus:** `stt-eval-seed@v2`
- **Registry state:** `ml/evaluation/manifests/resolution.json`, which
  resolves `intelliai-stt` for `en`, `hi`, and `ar` to whisper-small on
  the `stt-runtime` deployment. The runner was handed that resolution; it
  chose nothing, and refuses to run against a runtime not hosting what
  the registry resolved.

## 1. English — `intelliai-stt/en/whisper-small@1/cpu-int8/stt-eval-seed@v2`

Benchmark `2026-08-05-intelliai-stt-en-whisper-small-cpu-v1` ·
record `stt/results/2026-08-05-intelliai-stt-en.json`

| Metric | Value |
|---|---|
| Overall WER | **0.000** |
| Hallucinated words | 0 |
| Mean RTF | 0.150 |
| Clips | 4 (2 natural speech, 2 probes) |
| Quality claim | **yes** — natural speech with committed references |

`jfk-flac` and `jfk-wav` both transcribe exactly, reproducing the M2
baseline number on the same pinned clips. That is the point of carrying
v1's clips into v2 byte-identical: the English slice is comparable
backwards, so adding a language did not reset the platform's history.

## 2. Hindi — `intelliai-stt/hi/whisper-small@1/cpu-int8/stt-eval-seed@v2`

Benchmark `2026-08-05-intelliai-stt-hi-whisper-small-cpu-v1` ·
record `stt/results/2026-08-05-intelliai-stt-hi.json`

| Metric | Value |
|---|---|
| Overall WER | **null — no references in this slice** |
| Hallucinated words | 0 |
| Mean RTF | 1.786 |
| Clips | 2 (0 natural speech, 2 probes) |
| Quality claim | **no** — `coverage.is_quality_claim = false` |

**Read this record for what it is.** It measures the incumbent's
behaviour on Hindi-declared audio that contains no speech. It says
nothing about how well the product transcribes Hindi, because nothing in
this slice is Hindi speech. The record says so itself — `overall_wer` is
`null` and `natural_speech_clips` is `0` — rather than leaving a reader
to infer it from prose. **This slice cannot support promotion above the
`available` rung.**

What it does establish, and what was genuinely unmeasured before:

- **Hindi-declared silence and tone produce zero hallucinated words.**
  The pipeline's VAD short-circuit holds under a Hindi declaration; the
  language declaration does not open a hallucination path. Non-trivial —
  the engine is known to invent text on non-speech input when a language
  is forced.
- **A finding that matters operationally, below.**

### 2a. The declaration costs 9× on non-speech input

Identical 5-second tone clip, three declarations, median of three runs
each, same process:

| Declared | Inference | RTF |
|---|---|---|
| `en` | 1462.4 ms | 0.292 |
| `ar` | 1389.4 ms | 0.278 |
| **`hi`** | **13698.1 ms** | **2.740** |

Declaring Hindi makes the incumbent take **~9.4× longer** on audio that
contains no speech at all, and pushes it past real time (RTF > 1) on this
hardware. English and Arabic are indistinguishable from each other.

This is exactly the kind of thing evidence exists to find. It is recorded
here without a diagnosis: it could be decoder behaviour under a
low-resource language token, it could be an interaction with the VAD
short-circuit, it could be specific to this build. Diagnosing it is not
this milestone's job, and the number stands whether or not anyone likes
it. **It does mean the Hindi route's latency profile is not the English
route's**, and any capacity planning that assumed otherwise was wrong.

## 3. What is missing, and who decides it

The Hindi slice has no natural speech because the platform has **no Hindi
speech corpus**. The M2.5 corpus contains Hindi *text* (for synthesis);
transcription needs Hindi *audio* with committed reference transcripts,
which is a different asset entirely — a gap the design assumed away and
this step found.

Selecting or commissioning that corpus is a founder decision
(**F-M5-8**), the exact sibling of the Arabic corpus decision
(F-M5-6): it pins a third-party dataset — with its licence — into the
permanent, append-only evidence chain that every future Hindi promotion
will cite. That is not an engineering call to make quietly.

Until it exists, Hindi's honest ladder rung is `available`, which is
exactly where F-M5-2 put it.

## 4. Reproducing these

From records alone — no operator knowledge anywhere in the list:

```
identity.reproduction() ->
   model        intelliai-stt
   language     en
   dataset      stt-eval-seed@v2
   artifact     whisper-small@v1
   build        cpu-int8
   deployment   stt-runtime
```

The registry contributes the artifact through the manifest, the dataset
contributes the clips through its version, and the record contributes the
build and machine facts. Re-running both records reproduced them exactly:
identical transcripts, identical WER, identical hallucination counts. The
dataset is located by `name@version`, never by filename — a file can be
moved, a released version cannot change.
