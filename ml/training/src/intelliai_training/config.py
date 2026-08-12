"""Training configuration and run records — torch-free, fully typed.

A run is reproducible from its config + manifest hash + base revision +
seed, or it did not happen (FINE_TUNING_STRATEGY Part 10, law 6). The
config is frozen; the run record is the append-only research artifact.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LoraSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    rank: int = 32
    alpha: int = 64
    dropout: float = 0.05
    target_modules: tuple[str, ...] = ("q_proj", "v_proj")


class TrainingConfig(BaseModel):
    """Everything a training run needs, pinned before compute is spent."""

    model_config = ConfigDict(frozen=True)

    # The experiment this run belongs to — names the run record so a
    # conservative retrain (e1b) can never masquerade as the original.
    experiment: str = "e1-hi-lora"

    # Base lineage — the transformers checkpoint, pinned to a revision.
    base_model_id: str = "openai/whisper-small"
    base_revision: str  # commit sha of the HF repo, recorded at run time
    language: str = "hi"
    task: str = "transcribe"

    # Data
    manifest_path: str  # frozen train JSONL (5-field platform format)
    manifest_sha256: str  # pinned BEFORE training; re-verified at load
    data_root: str = "ml/datasets/data"
    validation_fraction: float = Field(default=0.03, ge=0.0, le=0.2)

    # LoRA
    lora: LoraSettings = LoraSettings()

    # Optimization
    learning_rate: float = 1e-3
    warmup_steps: int = 100
    max_steps: int = 4000
    per_device_batch_size: int = 8
    gradient_accumulation: int = 4  # effective batch 32
    gradient_checkpointing: bool = True
    precision: str = "bf16"  # Blackwell-native; no loss scaler needed
    max_grad_norm: float = 1.0
    seed: int = 20260811

    # Checkpoints
    output_dir: str = "weights/e1-hi-lora"
    checkpoint_every_steps: int = 500
    log_every_steps: int = 25


class SmokeReport(BaseModel):
    """What the smoke test proved, before the full run is funded."""

    model_config = ConfigDict(frozen=True)

    gpu_name: str
    vram_total_mib: int
    torch_version: str
    cuda_version: str
    python_version: str
    precision: str
    per_device_batch_size: int
    gradient_accumulation: int
    steps_run: int
    losses: tuple[float, ...]
    peak_vram_mib: float
    seconds_per_step: float
    checkpoint_roundtrip_ok: bool
    trainable_parameters: int
    total_parameters: int


class RunRecord(BaseModel):
    """The reproducibility record of one training run — append-only."""

    model_config = ConfigDict(frozen=True)

    experiment: str
    run_at: str  # ISO timestamp
    git_commit: str
    config: TrainingConfig
    environment: dict[str, str]
    train_samples: int
    validation_samples: int
    train_duration_seconds: float
    steps_completed: int
    final_train_loss: float
    validation_loss: float | None
    # (step, validation_loss) at every checkpoint boundary. E1 computed
    # validation ONCE, after the damage was done — overfitting was found
    # post-hoc. Monitoring during the run is what makes best-checkpoint
    # selection an evidence-based act instead of a guess.
    validation_history: tuple[tuple[int, float], ...] = ()
    peak_vram_mib: float
    checkpoint_dir: str
    checkpoint_sha256: str  # hash of the adapter safetensors
    notes: str = ""
