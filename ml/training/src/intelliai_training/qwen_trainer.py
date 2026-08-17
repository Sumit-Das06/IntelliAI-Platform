"""Qwen3-ASR SFT — the official recipe under our reproducibility laws.

Fidelity to the OFFICIAL `qwen3_asr_sft.py` (QwenLM/Qwen3-ASR/finetuning)
where it defines the FORMAT: the chat-template prefix (empty system
prompt + one audio user turn, generation prompt added) is masked to
-100; the supervised target is `language <Name><asr_text><text>` + EOS;
audio and text go through the wrapper's own processor in one call; the
loop is the HF Trainer.

Deliberate divergences, each carried by a config field and recorded in
the run record (never silent):

- seed              (the official script has none; law 6 requires one)
- gradient checkpointing + Adafactor + frozen audio tower
                    (full-SFT AdamW fp32 states alone exceed the 8 GiB
                     RTX 5070 — measured arithmetic, not taste)
- validation at every checkpoint boundary
                    (E1's lesson: overfitting found post-hoc is a wasted
                     run; monitoring makes checkpoint choice evidence)
- pinned base revision via local snapshot
                    (the wrapper takes a path; the path's bytes are the
                     recorded revision, verified by hf snapshot)

All torch/transformers/qwen-asr imports are lazy — importable (and
testable) without the `qwen-train` extra.
"""

from __future__ import annotations

import datetime
import json
import platform
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from intelliai_training.audio_io import CANONICAL_RATE, decode_to_float32
from intelliai_training.config import QwenRunRecord, QwenTrainingConfig, SmokeReport
from intelliai_training.qwen_manifest import convert_manifest

#: Module-name candidates for the audio tower. Freezing must find one or
#: refuse — a freeze that silently freezes nothing would train double the
#: parameters and lie about it.
_AUDIO_TOWER_NAMES = ("audio_tower", "audio_encoder", "speech_encoder", "audio_model")


def _seed_everything(seed: int) -> None:
    import random

    import numpy as np
    import torch

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def snapshot_base_model(config: QwenTrainingConfig, *, cache_dir: Path) -> Path:
    """Download (or reuse) the EXACT pinned revision into a local dir.

    The official wrapper loads by path/id without a revision argument;
    handing it a snapshot of the pinned revision makes the recorded
    identity and the trained bytes the same thing.
    """
    from huggingface_hub import snapshot_download

    # local_dir mode: real files, no symlinks — the hub's symlinked cache
    # needs a privilege Windows non-admin shells don't hold.
    target = cache_dir / f"qwen3-asr-0.6b-{config.base_revision[:12]}"
    path = Path(
        snapshot_download(
            config.base_model_id,
            revision=config.base_revision,
            local_dir=str(target),
        )
    )
    # The hub returns an EXISTING local_dir as-is when offline — which can
    # be a weightless shell from an interrupted fetch. Size-check the
    # weights every load; the fetch step verifies the full sha256 once.
    weights = path / "model.safetensors"
    if not weights.exists() or weights.stat().st_size != config.base_weights_bytes:
        actual = weights.stat().st_size if weights.exists() else 0
        msg = (
            f"base snapshot at {path} is incomplete: model.safetensors is "
            f"{actual} bytes, pinned {config.base_weights_bytes}. Re-run the "
            "fetch until the pinned bytes arrive — training from a partial "
            "base is not a thing."
        )
        raise RuntimeError(msg)
    return path


def load_wrapper(model_dir: Path, *, device_map: str | None = None) -> Any:
    """The official entry point: Qwen3ASRModel wraps model + processor."""
    import torch
    from qwen_asr import Qwen3ASRModel

    return Qwen3ASRModel.from_pretrained(
        str(model_dir),
        dtype=torch.bfloat16,
        device_map=device_map,
    )


def freeze_audio_tower(model: Any) -> tuple[int, int]:
    """Freeze the audio encoder; return (trainable, total) param counts.

    Looks for the tower under the known attribute names on the model or
    its `.model`; refuses loudly when none exists rather than training
    twice the parameters while claiming otherwise.
    """
    # The tower may nest (Qwen3-ASR wraps everything in a `thinker`
    # module, Omni-lineage naming) — search named modules structurally
    # and take the SHALLOWEST match so a submodule can never shadow it.
    matches = [
        (name.count("."), name, module)
        for name, module in model.named_modules()
        if name and name.rsplit(".", 1)[-1] in _AUDIO_TOWER_NAMES
    ]
    if not matches:
        names = [n for n, _ in model.named_children()]
        msg = (
            f"no audio tower found under {_AUDIO_TOWER_NAMES} anywhere in the model "
            f"(top-level children: {names}); refusing a freeze that would freeze nothing"
        )
        raise RuntimeError(msg)
    matches.sort(key=lambda entry: (entry[0], entry[1]))
    tower = matches[0][2]
    for parameter in tower.parameters():
        parameter.requires_grad = False
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    return trainable, total


def trainable_module(model: Any) -> Any:
    """The module that actually implements forward(input_ids, labels, …).

    The composite ``Qwen3ASRForConditionalGeneration`` is a generation
    shell with NO forward of its own; the trainable model is its
    ``thinker`` (Omni-lineage layout). Training the thinker mutates the
    composite's tensors in place — checkpoints are still saved from the
    COMPOSITE so the official wrapper can reload them.
    """
    import torch

    if type(model).forward is not torch.nn.Module.forward:
        return model
    thinker = getattr(model, "thinker", None)
    if thinker is None:
        msg = (
            f"{type(model).__name__} implements no forward and has no `thinker` "
            "submodule — the training surface of this architecture is unknown"
        )
        raise RuntimeError(msg)
    return thinker


def build_prefix_text(processor: Any) -> str:
    """The official prefix: empty system prompt + one audio user turn."""
    messages = [
        {"role": "system", "content": ""},
        {"role": "user", "content": [{"type": "audio", "audio": None}]},
    ]
    rendered = processor.apply_chat_template([messages], add_generation_prompt=True, tokenize=False)
    return str(rendered[0])


class QwenCollator:
    """The official collator, with our audio loader and a length guard.

    Prefix tokens and padding are masked to -100 exactly as the official
    script does; audio decodes through the platform's canonical loader
    (16 kHz mono float32 — identical samples to librosa on our already-
    canonical FLAC/WAV corpus, without the extra dependency).
    """

    def __init__(self, processor: Any, data_root: Path, prefix_text: str, max_seconds: float):
        self.processor = processor
        self.data_root = data_root
        self.prefix_text = prefix_text
        self.max_samples = int(max_seconds * CANONICAL_RATE)

    def __call__(self, features: list[dict[str, Any]]) -> dict[str, Any]:
        eos = self.processor.tokenizer.eos_token or ""
        full_texts = [self.prefix_text + f["text"] + eos for f in features]
        prefix_texts = [self.prefix_text for _ in features]
        audios = []
        for f in features:
            wave = decode_to_float32(self.data_root / f["audio"])
            if len(wave) > self.max_samples:
                msg = (
                    f"{f['audio']} exceeds the configured audio cap "
                    f"({len(wave) / CANONICAL_RATE:.1f}s); the frozen manifest "
                    "should never contain such a clip"
                )
                raise ValueError(msg)
            audios.append(wave)

        full = self.processor(
            text=full_texts, audio=audios, return_tensors="pt", padding=True, truncation=False
        )
        prefix = self.processor(
            text=prefix_texts, audio=audios, return_tensors="pt", padding=True, truncation=False
        )
        labels = full["input_ids"].clone()
        for i, prefix_len in enumerate(prefix["attention_mask"].sum(dim=1).tolist()):
            labels[i, :prefix_len] = -100
        pad_id = self.processor.tokenizer.pad_token_id
        if pad_id is not None:
            labels[labels == pad_id] = -100
        full["labels"] = labels
        return dict(full)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _sanitize_generation_config(model: Any) -> None:
    """Drop sampling-only flags the upstream config carries invalidly.

    The base repo ships `temperature: 1e-06` beside `do_sample: false`;
    transformers ignores it at runtime but REFUSES to save it. Unsetting
    changes no behavior (greedy decode ignores temperature) and makes
    checkpoints saveable.
    """
    for holder in (model, getattr(model, "thinker", None)):
        generation_config = getattr(holder, "generation_config", None)
        if generation_config is not None:
            generation_config.temperature = None
            generation_config.top_p = None
            generation_config.top_k = None


def _copy_inference_files(base_dir: Path, checkpoint_dir: Path) -> None:
    """Make a checkpoint loadable standalone (the official callback's job)."""
    for name in (
        "chat_template.json",
        "generation_config.json",
        "merges.txt",
        "preprocessor_config.json",
        "tokenizer_config.json",
        "vocab.json",
    ):
        source = base_dir / name
        if source.exists() and not (checkpoint_dir / name).exists():
            shutil.copy2(source, checkpoint_dir / name)


def _environment() -> dict[str, str]:
    import torch

    return {
        "python": platform.python_version(),
        "torch": torch.__version__,
        "cuda": torch.version.cuda or "cpu",
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "none",
        "platform": platform.platform(),
    }


def _git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],  # noqa: S607 — PATH lookup deliberate
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    return result.stdout.strip()


def _make_trainer(
    config: QwenTrainingConfig,
    model: Any,
    processor: Any,
    train_rows: list[dict[str, Any]],
    validation_rows: list[dict[str, Any]],
    *,
    output_dir: Path,
    max_steps: int | None = None,
    composite: Any = None,
    base_dir: Path | None = None,
) -> Any:
    import torch
    from transformers import Trainer, TrainerCallback, TrainingArguments

    class _InferableSnapshotCallback(TrainerCallback):  # type: ignore[misc]
        """Beside every trainer checkpoint, an `inferable/` composite copy.

        The trainer holds (and saves) the THINKER; the official wrapper
        loads the COMPOSITE. Saving the composite into a subdirectory
        keeps the trainer's own files untouched — resume still works —
        while every checkpoint stays evaluable through the wrapper.
        """

        def on_save(self, args: Any, state: Any, control: Any, **kwargs: Any) -> Any:
            checkpoint = Path(args.output_dir) / f"checkpoint-{state.global_step}"
            if composite is not None and checkpoint.is_dir():
                target = checkpoint / "inferable"
                _sanitize_generation_config(composite)
                composite.save_pretrained(str(target))
                processor.save_pretrained(str(target))
                if base_dir is not None:
                    _copy_inference_files(base_dir, target)
            return control

    if config.gradient_checkpointing:
        # Non-reentrant checkpointing backprops correctly even when some
        # inputs carry no grad (our frozen audio tower). The architecture
        # implements no get_input_embeddings, so the reentrant variant's
        # input-require-grads workaround is unavailable — and with a
        # trainable embedding layer, unnecessary.
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})

    collator = QwenCollator(
        processor,
        Path(config.data_root),
        build_prefix_text(processor),
        config.max_audio_seconds,
    )
    arguments = TrainingArguments(
        output_dir=str(output_dir),
        per_device_train_batch_size=config.per_device_batch_size,
        per_device_eval_batch_size=config.per_device_batch_size,
        gradient_accumulation_steps=config.gradient_accumulation,
        learning_rate=config.learning_rate,
        num_train_epochs=config.epochs,
        max_steps=max_steps if max_steps is not None else -1,
        logging_steps=config.log_steps,
        lr_scheduler_type="linear",
        warmup_ratio=config.warmup_ratio,
        optim=config.optimizer,
        max_grad_norm=config.max_grad_norm,
        seed=config.seed,
        data_seed=config.seed,
        bf16=config.precision == "bf16",
        save_strategy="steps",
        save_steps=config.save_steps,
        save_total_limit=config.save_total_limit,
        eval_strategy="steps" if validation_rows else "no",
        eval_steps=config.save_steps,
        dataloader_num_workers=0,  # deterministic, Windows-safe
        remove_unused_columns=False,
        report_to="none",
    )
    del torch
    return Trainer(
        model=model,
        args=arguments,
        train_dataset=train_rows,  # HF Trainer accepts list-of-dict datasets
        eval_dataset=validation_rows or None,
        data_collator=collator,
        callbacks=[_InferableSnapshotCallback()] if composite is not None else None,
    )


def smoke_test(
    config: QwenTrainingConfig,
    *,
    samples: int = 8,
    steps: int = 4,
    work_dir: Path,
) -> SmokeReport:
    """Phase 5: prove every moving part on THIS machine before funding a run.

    Load → freeze → collate real manifest audio → loss → backward →
    optimizer step (measured VRAM) → checkpoint save → reload →
    one real inference from the reloaded checkpoint.
    """
    import torch

    _seed_everything(config.seed)
    config = config.model_copy(update={"log_steps": 1})  # every smoke step's loss
    record = convert_manifest(
        Path(config.manifest_path),
        expected_sha256=config.manifest_sha256,
        output_dir=work_dir,
        language_tag=config.language_tag,
        validation_fraction=0.0,
    )
    rows = _read_jsonl(Path(record.train_path))[:samples]

    base_dir = snapshot_base_model(config, cache_dir=work_dir / "hf-cache")
    wrapper = load_wrapper(base_dir)
    model, processor = wrapper.model, wrapper.processor
    if config.freeze_audio_encoder:
        trainable, total = freeze_audio_tower(model)
    else:
        trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
        total = sum(p.numel() for p in model.parameters())
    model = model.cuda()

    torch.cuda.reset_peak_memory_stats()
    output_dir = work_dir / "smoke-checkpoint"
    trainer = _make_trainer(
        config,
        trainable_module(model),
        processor,
        rows,
        [],
        output_dir=output_dir,
        max_steps=steps,
    )
    started = time.perf_counter()
    result = trainer.train()
    elapsed = time.perf_counter() - started
    losses = tuple(
        round(entry["loss"], 4) for entry in trainer.state.log_history if "loss" in entry
    )
    peak_vram = torch.cuda.max_memory_allocated() / (1024 * 1024)

    # Save the COMPOSITE (its tensors were trained in place through the
    # thinker) so the official wrapper can reload the checkpoint.
    (output_dir / "final").mkdir(parents=True, exist_ok=True)
    _sanitize_generation_config(model)
    model.save_pretrained(str(output_dir / "final"))
    processor.save_pretrained(str(output_dir / "final"))
    _copy_inference_files(base_dir, output_dir / "final")

    # Reload the checkpoint THROUGH the official wrapper and transcribe
    # one real training clip — the roundtrip that proves the checkpoint
    # is a model, not a directory of tensors.
    del trainer, model, wrapper
    torch.cuda.empty_cache()
    reloaded = load_wrapper(output_dir / "final")
    first_audio = Path(config.data_root) / rows[0]["audio"]
    transcriptions = reloaded.transcribe(str(first_audio))
    first = transcriptions[0] if transcriptions else None
    roundtrip_ok = bool(first is not None and str(getattr(first, "text", "")).strip())

    return SmokeReport(
        gpu_name=torch.cuda.get_device_name(0),
        vram_total_mib=int(torch.cuda.get_device_properties(0).total_memory / (1024 * 1024)),
        torch_version=torch.__version__,
        cuda_version=torch.version.cuda or "cpu",
        python_version=platform.python_version(),
        precision=config.precision,
        per_device_batch_size=config.per_device_batch_size,
        gradient_accumulation=config.gradient_accumulation,
        steps_run=int(result.global_step),
        losses=losses,
        peak_vram_mib=round(peak_vram, 1),
        seconds_per_step=round(elapsed / max(int(result.global_step), 1), 2),
        checkpoint_roundtrip_ok=roundtrip_ok,
        trainable_parameters=trainable,
        total_parameters=total,
    )


def train(config: QwenTrainingConfig, *, max_steps: int | None = None) -> QwenRunRecord:
    """Pilot (bounded ``max_steps``) or full run — one code path."""
    import torch

    _seed_everything(config.seed)
    output_dir = Path(config.output_dir)
    record = convert_manifest(
        Path(config.manifest_path),
        expected_sha256=config.manifest_sha256,
        output_dir=output_dir,
        language_tag=config.language_tag,
        validation_fraction=config.validation_fraction,
    )
    train_rows = _read_jsonl(Path(record.train_path))
    validation_rows = _read_jsonl(Path(record.validation_path)) if record.validation_path else []

    # ONE shared base snapshot for every run (gitignored weights/): the
    # size check guards it, and a flaky resolver stops costing re-downloads.
    base_dir = snapshot_base_model(config, cache_dir=Path("weights/hf-base"))
    wrapper = load_wrapper(base_dir)
    model, processor = wrapper.model, wrapper.processor
    if config.freeze_audio_encoder:
        trainable, total = freeze_audio_tower(model)
    else:
        trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
        total = sum(p.numel() for p in model.parameters())
    model = model.cuda()

    torch.cuda.reset_peak_memory_stats()
    trainer = _make_trainer(
        config,
        trainable_module(model),
        processor,
        train_rows,
        validation_rows,
        output_dir=output_dir / "checkpoints",
        max_steps=max_steps,
        composite=model,
        base_dir=base_dir,
    )
    started = time.perf_counter()
    result = trainer.train()
    elapsed = time.perf_counter() - started

    validation_history = tuple(
        (int(entry["step"]), round(entry["eval_loss"], 4))
        for entry in trainer.state.log_history
        if "eval_loss" in entry
    )
    train_loss_history = tuple(
        (int(entry["step"]), round(entry["loss"], 4))
        for entry in trainer.state.log_history
        if "loss" in entry
    )
    final_loss = next(
        (entry["loss"] for entry in reversed(trainer.state.log_history) if "loss" in entry),
        float("nan"),
    )

    return QwenRunRecord(
        experiment=config.experiment,
        run_at=datetime.datetime.now(tz=datetime.UTC).isoformat(),
        git_commit=_git_commit(),
        config=config,
        environment=_environment(),
        train_jsonl_sha256=record.train_sha256,
        validation_jsonl_sha256=record.validation_sha256,
        train_samples=len(train_rows),
        validation_samples=len(validation_rows),
        trainable_parameters=trainable,
        total_parameters=total,
        train_duration_seconds=round(elapsed, 1),
        steps_completed=int(result.global_step),
        final_train_loss=round(float(final_loss), 4),
        train_loss_history=train_loss_history,
        validation_history=validation_history,
        peak_vram_mib=round(torch.cuda.max_memory_allocated() / (1024 * 1024), 1),
        checkpoint_dir=str(output_dir / "checkpoints"),
    )
