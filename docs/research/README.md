# docs/research/ — The Foundation Model Research Lab

The permanent knowledge base of IntelliAI's research program: the two
asset classes we permanently research — **foundation models** and
**datasets** — what we concluded about each, and the evidence behind
every conclusion. Customers see `intelliai-stt` and `intelliai-tts`;
this directory is where their replaceable engines (and the data assets
that will eventually outlast them) are researched before engineering
ever touches them.

- [RESEARCH_FRAMEWORK.md](RESEARCH_FRAMEWORK.md) — the governing process
  (IN FORCE, v0.2): status lifecycle, stage gates, licensing review,
  benchmarking rules, multilingual strategy, adoption/rejection criteria,
  fine-tune-vs-adopt decision tree, dataset research, technology watch,
  the data flywheel, and the living research priorities.
- [MODEL_LEDGER.md](MODEL_LEDGER.md) — the status of record for every
  researched model, with an **append-only** dated decision history.
- `models/` — per-candidate dossiers (drafted at Gate 2; mandatory for
  any model holding Promising status or later).
- **STT benchmark design** (Gate 3, design only — no measurement):
  [methodology](STT_BENCHMARK_METHODOLOGY.md) ·
  [record schema](STT_BENCHMARK_RECORD.md) ·
  [execution procedure](STT_BENCHMARK_PROCEDURE.md) ·
  [environment recording](STT_BENCHMARK_HARDWARE.md) ·
  [corpus specification](STT_BENCHMARK_CORPORA.md).
- Benchmark plans and adoption recommendations land here as standalone
  documents, cited from ledger entries.

How this directory relates to its neighbors:

- **`docs/` strategy stack** ([STRATEGY.md](../STRATEGY.md)) holds the
  instruments this lab uses — the scoring framework
  ([FOUNDATION_MODELS.md §1](../FOUNDATION_MODELS.md)), licensing policy
  ([ADR-0005](../adr/0005-permissive-model-licensing-policy.md)), and
  fine-tuning framework ([FINE_TUNING_STRATEGY.md](../FINE_TUNING_STRATEGY.md)).
  This lab produces *research conclusions*; the strategy stack defines
  *how to reach them*.
- **`ml/evaluation/`** is the evaluation plane — the only source of
  numbers this lab may cite as evidence
  ([SPEECH_EVALUATION.md](../../ml/evaluation/SPEECH_EVALUATION.md)).
- **`research/` at the repo root** is the *code* sandbox (experiments,
  notebooks). This directory is the *knowledge base* — documents only,
  never code.

Research recommends; the founder decides; engineering adopts. Nothing in
this directory ships anything.
