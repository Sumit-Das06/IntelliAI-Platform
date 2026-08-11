"""The E1 LoRA training loop: deterministic, measured, checkpointed.

All torch/transformers/peft imports are lazy — the module is importable
(and its callers testable) without the `train` extra. The loop follows
the canonical Whisper fine-tuning recipe (feature extractor + tokenizer
with language/task prefix tokens, labels padded to -100, model-internal
shift) with PEFT LoRA attached, bf16 autocast on Blackwell, gradient
accumulation and checkpointing, and hard VRAM measurement.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import platform
import subprocess
import time
from pathlib import Path
from typing import Any

from intelliai_training.audio_io import CANONICAL_RATE, decode_to_float32
from intelliai_training.config import RunRecord, SmokeReport, TrainingConfig
from intelliai_training.manifest import TrainSample, load_manifest, split_validation


def _seed_everything(seed: int) -> None:
    import random

    import numpy as np
    import torch

    random.seed(seed)
    np.random.seed(seed)  # legacy global API is what our deps consume
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def _load_model_and_processor(config: TrainingConfig) -> tuple[Any, Any]:
    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import WhisperForConditionalGeneration, WhisperProcessor

    processor = WhisperProcessor.from_pretrained(
        config.base_model_id,
        revision=config.base_revision,
        language="hindi" if config.language == "hi" else config.language,
        task=config.task,
    )
    model: Any = WhisperForConditionalGeneration.from_pretrained(
        config.base_model_id,
        revision=config.base_revision,
        torch_dtype=torch.float32,
    )
    model.config.forced_decoder_ids = None
    model.config.suppress_tokens = []
    if config.gradient_checkpointing:
        model.gradient_checkpointing_enable()
        model.enable_input_require_grads()
    lora = LoraConfig(
        r=config.lora.rank,
        lora_alpha=config.lora.alpha,
        lora_dropout=config.lora.dropout,
        target_modules=list(config.lora.target_modules),
        bias="none",
    )
    model = get_peft_model(model, lora)
    return model.cuda(), processor


def _batches(
    samples: list[TrainSample],
    processor: Any,
    config: TrainingConfig,
    *,
    shuffle_epoch: int | None,
) -> Any:
    """Yield collated batches; deterministic shuffle per epoch."""
    import numpy as np
    import torch

    order = list(range(len(samples)))
    if shuffle_epoch is not None:
        rng = np.random.default_rng(config.seed + shuffle_epoch)
        rng.shuffle(order)
    data_root = Path(config.data_root)
    tokenizer = processor.tokenizer
    feature_extractor = processor.feature_extractor
    batch_size = config.per_device_batch_size

    for start in range(0, len(order), batch_size):
        chunk = [samples[i] for i in order[start : start + batch_size]]
        features = feature_extractor(
            [decode_to_float32(data_root / s.audio) for s in chunk],
            sampling_rate=CANONICAL_RATE,
            return_tensors="pt",
        ).input_features
        labels = tokenizer([s.text for s in chunk], return_tensors="pt", padding=True).input_ids
        labels = labels.masked_fill(labels == tokenizer.pad_token_id, -100)
        if (labels[:, 0] == tokenizer.bos_token_id).all():
            labels = labels[:, 1:]
        yield {
            "input_features": features.cuda(),
            "labels": torch.as_tensor(labels).cuda(),
        }


def _checkpoint(model: Any, directory: Path, step: int, loss: float) -> Path:
    target = directory / f"checkpoint-{step}"
    model.save_pretrained(str(target))
    (target / "trainer_state.json").write_text(
        json.dumps({"step": step, "loss": loss}) + "\n", encoding="utf-8"
    )
    return target


def _adapter_sha256(checkpoint_dir: Path) -> str:
    weights = sorted(checkpoint_dir.glob("adapter_model.*"))
    if not weights:
        return ""
    digest = hashlib.sha256()
    for path in weights:
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _checkpoint_roundtrip_ok(checkpoint_dir: Path) -> bool:
    """The written adapter must be readable and non-trivial."""
    from safetensors.torch import load_file

    weights = checkpoint_dir / "adapter_model.safetensors"
    if not weights.exists():
        return False
    tensors = load_file(str(weights))
    return len(tensors) > 0 and all(t.numel() > 0 for t in tensors.values())


def _environment() -> dict[str, str]:
    import torch

    env = {
        "python": platform.python_version(),
        "torch": torch.__version__,
        "cuda": torch.version.cuda or "none",
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "none",
        "os": f"{platform.system()} {platform.release()}",
    }
    try:
        env["git_commit"] = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607 — PATH lookup deliberate
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        env["git_commit"] = "unknown"
    return env


def run(
    config: TrainingConfig,
    *,
    smoke: bool = False,
    smoke_steps: int = 5,
    smoke_samples: int = 24,
) -> SmokeReport | RunRecord:
    import torch

    if not torch.cuda.is_available():
        msg = "CUDA is not available; the E1 experiment requires the local GPU"
        raise RuntimeError(msg)

    _seed_everything(config.seed)
    samples = load_manifest(Path(config.manifest_path), expected_sha256=config.manifest_sha256)
    train_samples, val_samples = split_validation(samples, fraction=config.validation_fraction)
    if smoke:
        train_samples = train_samples[:smoke_samples]
        val_samples = []

    model, processor = _load_model_and_processor(config)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())

    optimizer = torch.optim.AdamW(
        (p for p in model.parameters() if p.requires_grad),
        lr=config.learning_rate,
    )
    max_steps = smoke_steps if smoke else config.max_steps

    def lr_lambda(step: int) -> float:
        if step < config.warmup_steps:
            return step / max(config.warmup_steps, 1)
        remaining = max(max_steps - config.warmup_steps, 1)
        return max(0.0, (max_steps - step) / remaining)

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)

    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "config.json").write_text(
        config.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )

    torch.cuda.reset_peak_memory_stats()
    autocast_dtype = torch.bfloat16 if config.precision == "bf16" else torch.float16
    model.train()
    losses: list[float] = []
    step = 0
    epoch = 0
    started = time.perf_counter()
    accumulating = 0
    running_loss = 0.0

    while step < max_steps:
        for batch in _batches(train_samples, processor, config, shuffle_epoch=epoch):
            with torch.autocast("cuda", dtype=autocast_dtype):
                loss = model(**batch).loss / config.gradient_accumulation
            loss.backward()
            running_loss += float(loss.detach()) * config.gradient_accumulation
            accumulating += 1
            if accumulating < config.gradient_accumulation:
                continue
            torch.nn.utils.clip_grad_norm_(model.parameters(), config.max_grad_norm)
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad(set_to_none=True)
            step += 1
            mean_loss = running_loss / config.gradient_accumulation
            losses.append(round(mean_loss, 4))
            running_loss = 0.0
            accumulating = 0
            if step % config.log_every_steps == 0 or smoke:
                elapsed = time.perf_counter() - started
                print(
                    f"step {step}/{max_steps} loss {mean_loss:.4f} "
                    f"lr {scheduler.get_last_lr()[0]:.2e} "
                    f"vram {torch.cuda.max_memory_allocated() / (1 << 20):.0f}MiB "
                    f"{elapsed / step:.2f}s/step"
                )
            if not smoke and step % config.checkpoint_every_steps == 0:
                _checkpoint(model, output_dir, step, mean_loss)
            if step >= max_steps:
                break
        epoch += 1

    duration = time.perf_counter() - started
    final_checkpoint = _checkpoint(model, output_dir, step, losses[-1] if losses else 0.0)
    peak_vram = torch.cuda.max_memory_allocated() / (1 << 20)
    env = _environment()

    if smoke:
        finite = all(l == l and abs(l) < 1e4 for l in losses)  # noqa: E741
        if not finite:
            msg = f"smoke test produced non-finite losses: {losses}"
            raise RuntimeError(msg)
        return SmokeReport(
            gpu_name=env["gpu"],
            vram_total_mib=int(torch.cuda.get_device_properties(0).total_memory / (1 << 20)),
            torch_version=env["torch"],
            cuda_version=env["cuda"],
            python_version=env["python"],
            precision=config.precision,
            per_device_batch_size=config.per_device_batch_size,
            gradient_accumulation=config.gradient_accumulation,
            steps_run=step,
            losses=tuple(losses),
            peak_vram_mib=round(peak_vram, 1),
            seconds_per_step=round(duration / max(step, 1), 2),
            checkpoint_roundtrip_ok=_checkpoint_roundtrip_ok(final_checkpoint),
            trainable_parameters=trainable,
            total_parameters=total,
        )

    validation_loss: float | None = None
    if val_samples:
        model.eval()
        val_losses: list[float] = []
        with torch.no_grad():
            for batch in _batches(val_samples, processor, config, shuffle_epoch=None):
                with torch.autocast("cuda", dtype=autocast_dtype):
                    val_losses.append(float(model(**batch).loss))
        validation_loss = round(sum(val_losses) / max(len(val_losses), 1), 4)

    return RunRecord(
        experiment="e1-hi-lora",
        run_at=datetime.datetime.now(tz=datetime.UTC).isoformat(),
        git_commit=env["git_commit"],
        config=config,
        environment=env,
        train_samples=len(train_samples),
        validation_samples=len(val_samples),
        train_duration_seconds=round(duration, 1),
        steps_completed=step,
        final_train_loss=losses[-1] if losses else float("nan"),
        validation_loss=validation_loss,
        peak_vram_mib=round(peak_vram, 1),
        checkpoint_dir=str(final_checkpoint),
        checkpoint_sha256=_adapter_sha256(final_checkpoint),
    )
