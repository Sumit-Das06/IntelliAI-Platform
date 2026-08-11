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
  documents, cited from ledger entries. Current standalone reports:
  [2026-08-10-first-finetuning-experiment.md](2026-08-10-first-finetuning-experiment.md)
  — fine-tuning base + public-dataset research, recommendation
  (whisper-small · Hindi · LoRA), and the E1 experiment design.
  [2026-08-11-small-asr-model-strategy.md](2026-08-11-small-asr-model-strategy.md)
  — small-model / modular multilingual strategy across EN·HI·AR·TA·ML·ZH:
  hybrid-pool architecture, TA/ML/ZH model+dataset screens, routing and
  call-center concurrency analysis, two-arm first experiment.
  [2026-08-11-15b-ingestion-baseline-report.md](2026-08-11-15b-ingestion-baseline-report.md)
  — Milestone 15B close-out: frozen public-data manifests, the first
  Hindi baseline (whisper-small CER 0.2919), Qwen3-ASR 0.6B CPU spike
  readings, blocked-evaluation verdicts, and the 15C/15D recommendation.
  [2026-08-11-15c-hindi-eval-baseline.md](2026-08-11-15c-hindi-eval-baseline.md)
  — Milestone 15C close-out: gated access unblocked, the speaker-disjoint
  primary `stt-hi-public-eval@v1`, and the OFFICIAL Hindi baseline
  (whisper-small CER 0.3629) with documented engine variance.
  [2026-08-11-15d-e1-hindi-lora.md](2026-08-11-15d-e1-hindi-lora.md)
  — Milestone 15D close-out: the first fine-tuning experiment, end to
  end on the local GPU — and an honestly measured FAILURE (candidate
  CER 0.9049 vs baseline 0.3629; rejected), with the training machinery
  proven and remediation hypotheses recorded.

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
