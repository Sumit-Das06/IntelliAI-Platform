# ml/datasets — Public-Data Ingestion & Dataset Manifests

The dataset plane of the training program (FINE_TUNING_STRATEGY Part 3;
RESEARCH_FRAMEWORK §12). It turns *screened public sources* into
*deterministic, hash-pinned manifests* that the evaluation plane and a
future training pipeline consume.

## Module charter

**Why it exists.** Training and evaluation may only consume data whose
license, provenance, and integrity are recorded — and the record must be
reproducible. Ad-hoc downloads produce numbers nobody can defend a year
later; this package makes the ingestion itself an auditable artifact.

**Responsibilities it owns**

- the source registry: one dated, license-verdict record per public
  source, including sources we *cannot* access yet (blocked is a status,
  not an omission);
- ingestion of approved open sources into a local, gitignored data root
  (original bytes, SHA-256 identity per clip);
- deterministic validation with an explicit rejection reason per sample;
- deterministic curation (stable content-hash ordering, duration budget);
- writing manifests: evaluation manifests in `intelliai_evaluation`'s
  `EvalDataset` schema (path-source clips), and training manifests in
  the platform's 5-field JSONL format with a provenance sidecar.

**Responsibilities it must NEVER own**

- training or fine-tuning (that is `ml/training`, when it opens);
- scoring or metrics (that is `ml/evaluation` — one evaluation framework);
- production data: nothing here may read the platform database, object
  storage, or any customer/consented audio;
- serving anything.

**May communicate with**: `intelliai_evaluation` (imports its manifest
schema — one schema, never a second), the public internet (pinned
dataset downloads only).

**Must never depend on**: `apps/api`, the runtimes, `packages/runtime-core`
(no ArtifactStore — datasets are not model weights), any database.

**Scalability**: each source is one adapter module producing the same
`CandidateSample` stream; validation/curation/manifest layers are
source-agnostic, so unlocking a gated source later adds one adapter and
zero changes elsewhere.

## Layout

- `src/intelliai_datasets/sources.py` — the source registry (licenses,
  access status, contamination risk; all dated).
- `src/intelliai_datasets/audio.py` — WAV probing + hashing.
- `src/intelliai_datasets/ingest_fleurs.py` — FLEURS parquet adapter
  (open source; no HF account needed).
- `src/intelliai_datasets/validate.py` — validation + rejection reasons.
- `src/intelliai_datasets/curate.py` — deterministic selection.
- `src/intelliai_datasets/manifests.py` — train JSONL + eval manifest
  writers, hash pinning.
- `manifests/` — committed manifest + provenance + validation-report
  files (text only; audio lives under `data/`, which is gitignored).

Audio is NEVER committed: `data/` and all audio extensions are covered
by the root `.gitignore`.
