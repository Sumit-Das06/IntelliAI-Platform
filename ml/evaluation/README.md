# ml/evaluation — Evaluation Seed

The ruler every model is measured against. Models change; the benchmark
must not (PRD operating principles; Constitution P9–P11). This package is
the *seed* of the M9 evaluation harness: deliberately small, but the
discipline — versioned immutable datasets, one metric implementation,
one recording format — starts here, before the first model is downloaded.

Speech **generation** evaluation (TTS and successors) is governed by
[SPEECH_EVALUATION.md](SPEECH_EVALUATION.md) (M2.5): the metric
hierarchy with declared directions, the judge discipline for round-trip
intelligibility, the structured listening protocol, and the extension
recipe for future capabilities.

## Module charter (the six questions)

1. **Why does this module exist?** So that "is this model better?" has an
   answer before any model exists to ask it about. Every engine adapter,
   fine-tune, and replacement decision (the switching test) cites results
   produced here.
2. **What does it own?** Evaluation dataset manifests (versioned,
   immutable), metric implementations (WER v1), the benchmark result
   format, and clip materialization (download + hash verification,
   deterministic synthetic generation).
3. **What does it explicitly NOT own?** Running inference (runtimes do),
   model weights (ModelManager does), quality *judgments* (humans do,
   citing results), the full evaluation-identity system (reserved for M9
   — MODEL_IDENTITY §11), training data (the dataset registry's future
   concern — eval sets never train, AI_STRATEGY §2).
4. **What does it depend on?** pydantic (manifest/result schemas), httpx
   (clip download), `packages/runtime-contract` (the frozen `Capability`
   enum — the step 0 local-Literal debt was paid at M2 step 1), stdlib
   only for metrics and synthesis. Never on engines, never on the gateway.
5. **Who depends on it?** The STT runtime's local real-model test tier
   (step 5), milestone close-out measurements, and eventually the M9
   harness, which grows from this package rather than replacing it.
6. **How does it evolve?** Dataset changes are new *versions* (manifests
   are immutable once released — same law as migrations and artifacts);
   metrics are added, never silently changed (a changed metric is a new
   metric name); the results schema is additive-only.

## Datasets

Released versions are immutable. A change is always the **next** version,
never an edit — so what a years-old record cites still resolves.

- **`stt-eval-seed@v1`** (`stt/datasets/stt-eval-v1.json`) — the seed set:
  2 public-domain speech clips with exact reference transcripts (pinned
  URLs + SHA-256; audio is **never committed** — the large-file guard and
  the weights rule apply to eval data too) and 2 deterministic synthetic
  probes (silence, tone) with empty references, so Whisper's documented
  silence-hallucination failure mode is probed from day one.
- **`stt-eval-seed@v2`** (`stt/datasets/stt-eval-v2.json`) — **current.**
  v1's four clips plus four language-tagged probes (`en`, `hi` silence and
  tone), added in M5 so a language slice could be measured at all. It is
  what every current record cites and what `make eval-fetch` materializes.

**What v2 is not.** It carries **no natural speech outside English**: its
`hi` slice is two synthetic probes with empty references, which is why the
Hindi record reads `is_quality_claim: false`. Its English slice is two
natural clips — the same ~11-second utterance in two containers. Both facts
are honest properties of the manifest, and both are why no promotion above
`available` can rest on it.

### Recording protocol (founder homework)

Because reference transcripts must be *exact*, the reference is written
first and read aloud, not transcribed afterwards:

1. **Script first.** Write each passage down (5 English, 5 Hindi;
   2–4 sentences each; include numbers, names, and one technical term
   per passage — the things STT gets wrong). The written text IS the
   reference; read it verbatim.
2. **Record** one WAV per passage: quiet room, phone or headset mic at a
   normal distance, 16 kHz or higher, mono preferred. 10–30 s each.
   Natural pace — this corpus should sound like a real user, not a
   voice-over.
3. **Name and place:** `en-read-01.wav` … `hi-read-05.wav` into
   `ml/evaluation/corpus-inbox/`. That directory and every audio
   extension are gitignored: a corpus we built and never published is
   the only structurally clean position against training-data
   contamination, and publication cannot be undone.
4. Then the manifests get built: each file is SHA-256-pinned, reference
   text attached, and the recordings release as **`stt-eval-seed@v3`** —
   not v2. v2 is already released and immutable; the next version is the
   only place new clips can go.

**Two things block step 4 today, and they are not homework:**

- **`EvalClip` has no local-path source.** `_exactly_one_source` permits a
  pinned URL + SHA-256 or a synthetic spec, and nothing else — so audio we
  record ourselves is currently unregisterable. Private clips stay local
  until either the schema gains a `path` source or object storage lands.
- **Hindi must not be scored before its ruler exists.** `normalize_words`
  strips to `[^a-z0-9\s']+`, so a Devanagari reference normalises to an
  empty word list: a *perfectly* transcribed Hindi clip would be recorded
  as N hallucinated words with no WER, permanently, in an append-only
  ledger. Recording Hindi is safe; running it through this path is not.

## Usage

```bash
make eval-fetch      # materialize clips into ml/evaluation/data/ (gitignored)

# Measure one LIVE slice (end-to-end over HTTP — the product's numbers).
# `hardware`, `out` and `engine_version` have no defaults; see below.
make eval lang=en engine_version=1.2.1 \
     hardware="<cpu description>" \
     out=ml/evaluation/stt/results/<date>-intelliai-stt-en.json
```

The same thing without make, which is what the target runs:

```bash
uv run --package intelliai-evaluation python -m intelliai_evaluation run \
  --dataset ml/evaluation/stt/datasets/stt-eval-v2.json \
  --manifest ml/evaluation/manifests/resolution.json \
  --url http://localhost:8001 \
  --model intelliai-stt --language en \
  --engine faster-whisper --engine-version <x.y.z> --compute cpu-int8 \
  --hardware "<cpu description>" \
  --out ml/evaluation/stt/results/<date>-intelliai-stt-en.json
```

**There is no `--artifact` flag, deliberately.** A run measures one
*slice* — one public model, one language — and the artifact comes from
the registry's exported resolution manifest, never from the operator. A
benchmark against an artifact somebody named records a claim; a benchmark
against the artifact the registry resolved records what the product
actually serves. The runner then refuses to write anything if the runtime
is not hosting that artifact.

**`--hardware` has no default anywhere**, including in the make target.
It is a free string today and the one machine we own is already spelled
four ways across committed records; a default would quietly mint a fifth
and make it canonical. The structured replacement is designed
(`docs/research/hardware-profiles.md`) and not yet ratified.

Results are recorded as JSON conforming to `results.EvalRun`, committed
under `stt/results/` (small, text, append-only): one file per run.
Aggregates: word-weighted overall WER across non-empty-reference clips;
mean RTF; total hallucinated words on empty-reference clips.

### Speech synthesis evaluation (the reproducible workflow)

One command turns a committed corpus plus two live runtimes into one
immutable `SpeechEvalRun`. Reproducibility metadata is taken from live
facts (`/info` of both runtimes), and the run refuses to start if the
synthesis runtime is not serving the artifact named — a record that
misnames its subject would poison the ledger.

```bash
# Runtimes: tts-runtime with the evaluated engine, stt-runtime (whisper)
# as the judge. This regenerates the kokoro-82m baseline evidence
# (latencies are measurements of the moment; transcripts and WER are
# properties of the artifacts and should reproduce):
make speech-eval hardware="<cpu description>" \
     out=ml/evaluation/tts/results/<date>-kokoro-82m.json
```

Comparisons hold **only within one judge identity, including its host**:
in our own committed `kokoro-82m` / `-repro` pair the judge artifact and
version were identical, yet 9 of 25 transcripts differed and RTF moved
+27.5% — because the judge ran on a different machine.

Ledger law (SPEECH_EVALUATION.md §5): `tts/results/` is append-only —
re-runs and corrections are NEW records citing the old (`--notes`,
`--baseline-name` only when a run is christened a named baseline);
comparisons are valid only within one judge identity.
