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

- `stt/datasets/stt-eval-v1.json` — the seed set: 2 public-domain speech
  clips with exact reference transcripts (pinned URLs + SHA-256; audio is
  **never committed** — the large-file guard and the weights rule apply
  to eval data too) and 2 deterministic synthetic probes (silence, tone)
  with empty references — Whisper's documented silence-hallucination
  failure mode is probed from day one.
- **v2 (pending recordings):** v1 plus founder-recorded English + Hindi
  read speech — the first wedge-aligned measurements and the start of the
  long-term evaluation corpus. v2 releases when the recordings below
  exist; manifests are immutable, so it is not created ahead of them.

### Recording protocol for the v2 corpus (founder homework)

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
   `ml/evaluation/corpus-inbox/` (gitignored staging dir).
4. Then the manifests get built: each file is SHA-256-pinned, reference
   text attached, and `stt-eval-v2.json` released with v1's clips
   included unchanged. Hosting: private clips stay local-path pinned
   until object storage lands (MinIO/S3) — the manifest schema gains a
   `path` source alongside `url`/`synthetic` at that point.

## Usage

```bash
make eval-fetch      # materialize clips into ml/evaluation/data/ (gitignored)

# Measure a LIVE runtime (end-to-end over HTTP — the product's numbers):
uv run --package intelliai-evaluation python -m intelliai_evaluation run \
  --dataset ml/evaluation/stt/datasets/stt-eval-v1.json \
  --url http://localhost:8001 --artifact whisper-small \
  --engine faster-whisper --engine-version <x.y.z> --compute cpu-int8 \
  --hardware "<cpu description>" --out ml/evaluation/stt/results/<date>-<artifact>.json
```

Results are recorded as JSON conforming to `results.EvalRun`, committed
under `stt/results/` (small, text, append-only): one file per run,
named `YYYY-MM-DD-<artifact>.json`. Aggregates: word-weighted overall
WER across non-empty-reference clips; mean RTF; total hallucinated words
on empty-reference clips.
