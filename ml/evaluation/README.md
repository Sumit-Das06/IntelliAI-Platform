# ml/evaluation — Evaluation Seed

The ruler every model is measured against. Models change; the benchmark
must not (PRD operating principles; Constitution P9–P11). This package is
the *seed* of the M9 evaluation harness: deliberately small, but the
discipline — versioned immutable datasets, one metric implementation,
one recording format — starts here, before the first model is downloaded.

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
- **v2 (planned, step 5):** curated real-world clips including
  user-recorded English + Hindi read speech — the first wedge-aligned
  measurements.

## Usage

```bash
make eval-fetch      # materialize clips into ml/evaluation/data/ (gitignored)
```

Results are recorded as JSON conforming to `results.EvalRun`, committed
under `stt/results/` (small, text, append-only): one file per run,
named `YYYY-MM-DD-<artifact>.json`. Aggregates: word-weighted overall
WER across non-empty-reference clips; mean RTF; total hallucinated words
on empty-reference clips.
