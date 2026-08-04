# docs/research/ — The Foundation Model Research Lab

The permanent knowledge base of IntelliAI's model research program:
which foundation models we have examined, what we concluded, and the
evidence behind every conclusion. Customers see `intelliai-stt` and
`intelliai-tts`; this directory is where their replaceable engines are
researched before engineering ever touches them.

- [RESEARCH_FRAMEWORK.md](RESEARCH_FRAMEWORK.md) — the governing process:
  status lifecycle, stage gates, licensing review, benchmarking rules,
  multilingual strategy, adoption/rejection criteria, fine-tune-vs-adopt
  decision tree.
- [MODEL_LEDGER.md](MODEL_LEDGER.md) — the status of record for every
  researched model, with an **append-only** dated decision history.
- `models/` — per-candidate dossiers (created when a candidate reaches
  Gate 2 of the framework).
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
