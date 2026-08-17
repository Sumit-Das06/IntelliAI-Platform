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


class QwenTrainingConfig(BaseModel):
    """Milestone 21: Qwen3-ASR SFT, following the OFFICIAL recipe.

    The official `qwen3_asr_sft.py` (QwenLM/Qwen3-ASR/finetuning) is the
    source of truth for the training FORMAT (JSONL rows, chat-template
    prefix masked to -100, target `language <Name><asr_text>text` + EOS,
    HF Trainer). This config adds what that script lacks and our laws
    require: a seed, gradient checkpointing, an optimizer whose states
    FIT 8 GiB (full-SFT AdamW fp32 states alone exceed the card), an
    encoder freeze, and per-checkpoint validation monitoring. Every
    divergence from the official defaults is a field here — recorded,
    never silent.
    """

    model_config = ConfigDict(frozen=True)

    experiment: str = "qwen-e1-hi-sft"

    # Base identity — the HF training checkpoint, pinned to the revision
    # the 15E research recorded (unchanged upstream since 2026-01-30).
    # The serving GGUFs keep their own identity; this never touches them.
    base_model_id: str = "Qwen/Qwen3-ASR-0.6B"
    base_revision: str = "5eb144179a02acc5e5ba31e748d22b0cf3e303b0"
    #: LFS sha256 of model.safetensors at that revision (HF API, recorded
    #: 2026-08-17) — the trained-from bytes, verifiable offline forever.
    base_weights_sha256: str = "79d6cbd4c98c7bbffe9db2edac07f56cd6637d0d5944b27f6c2b8353840323ea"
    base_weights_bytes: int = 1_876_091_704
    language: str = "hi"
    #: The official JSONL text prefix for this language — MUST match what
    #: the model emits and the serving adapter parses (`parse_asr_output`).
    language_tag: str = "Hindi"

    # Data — the frozen 5-field platform manifest; conversion to the
    # official JSONL is deterministic and hash-recorded (qwen_manifest).
    manifest_path: str = "ml/datasets/manifests/hi-public-train-v1.jsonl"
    manifest_sha256: str = "a4748dee8a7a82ee4e1233587f3f4366fba91dfcb1e367415191e2e3388ee0df"
    data_root: str = "ml/datasets/data"
    validation_fraction: float = Field(default=0.03, ge=0.0, le=0.2)

    # What trains. Full-parameter SFT is the official shape; freezing the
    # audio tower is OUR conservative default — the 15E error analysis
    # showed text-side errors, not acoustic ones, and the frozen tower
    # roughly halves optimizer/gradient memory on an 8 GiB card.
    freeze_audio_encoder: bool = True

    # Optimization. Official defaults are lr 2e-5 at effective batch 128
    # on server GPUs; scaled here for effective batch 16 and a 10 h
    # corpus. Adafactor's factored states are what make full SFT fit.
    optimizer: str = "adafactor"  # adafactor | adamw_torch (VRAM permitting)
    learning_rate: float = 1e-5
    epochs: float = 2.0
    per_device_batch_size: int = 2
    gradient_accumulation: int = 8  # effective batch 16
    warmup_ratio: float = 0.03
    gradient_checkpointing: bool = True
    precision: str = "bf16"  # Blackwell-native, matches the official cap>=8 path
    max_grad_norm: float = 1.0
    seed: int = 20260817
    max_audio_seconds: float = 30.0  # manifest curation cap; guards the collator

    # Checkpoints
    output_dir: str = "weights/qwen-e1-hi-sft"
    save_steps: int = 150
    save_total_limit: int = 6
    log_steps: int = 10


class QwenRunRecord(BaseModel):
    """Reproducibility record of one Qwen SFT run — append-only."""

    model_config = ConfigDict(frozen=True)

    experiment: str
    run_at: str
    git_commit: str
    config: QwenTrainingConfig
    environment: dict[str, str]
    #: SHA-256 of the DERIVED official-format JSONLs actually trained on.
    train_jsonl_sha256: str
    validation_jsonl_sha256: str | None
    train_samples: int
    validation_samples: int
    trainable_parameters: int
    total_parameters: int
    train_duration_seconds: float
    steps_completed: int
    final_train_loss: float
    #: (step, windowed train loss) for every logging boundary — the E1b
    #: pilot showed the last window alone can mislead (batch spikes).
    train_loss_history: tuple[tuple[int, float], ...] = ()
    validation_history: tuple[tuple[int, float], ...] = ()
    peak_vram_mib: float
    checkpoint_dir: str
    notes: str = ""


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
