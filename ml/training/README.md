# ml/training — Fine-Tuning Pipelines

The training plane: manifest-driven, reproducible fine-tuning of
foundation models on frozen public-data manifests. Research plane only —
its outputs are candidate artifacts for the switching test, never
production deployments.

## Module charter

**Why it exists.** The fine-tuning ladder (FINE_TUNING_STRATEGY Part 2)
needs a place where training runs are reproducible artifacts: pinned
base revision + frozen manifest hash + recorded recipe, or the run did
not happen (Part 10, law 6).

**Owns**: LoRA/PEFT training loops over frozen JSONL manifests; smoke
tests proving a configuration before it is funded; run records
(environment, VRAM, loss, durations, hashes); adapter merge and
serving-format conversion of candidates.

**Must NEVER own**: dataset ingestion/curation (`ml/datasets`), scoring
(`ml/evaluation` — one evaluation framework), serving (runtimes),
production promotion (registry/engineering), any customer or production
data.

**May communicate with**: `intelliai_datasets` (manifest shapes),
`intelliai_evaluation` (dataset schema for eval manifests), local disk,
the GPU.

**Must never depend on**: `apps/api`, the runtimes, any database or
object store.

**Scaling**: one recipe module per experiment family; the heavy stack
(torch/transformers/peft) is an optional `train` extra installed only
where training runs — CI tests the torch-free layers (config, manifest
loading, hashing, provenance) and never downloads CUDA wheels.

Install for training (GPU machine):

    uv sync --all-packages --extra train --extra whisper
