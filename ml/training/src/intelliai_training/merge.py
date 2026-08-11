"""Merge the LoRA adapter into the base and convert for serving.

Research artifacts only: the adapter stays preserved beside the merged
model (the merge is derived, the adapter is the training output), and
the CT2 conversion stores float32 weights — precision is a LOAD concern
(ADR-0015), exactly like the incumbent artifact.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from intelliai_training.config import TrainingConfig


def merge_adapter(config: TrainingConfig, checkpoint_dir: Path, merged_dir: Path) -> None:
    import torch
    from peft import PeftModel
    from transformers import WhisperForConditionalGeneration, WhisperProcessor

    base = WhisperForConditionalGeneration.from_pretrained(
        config.base_model_id,
        revision=config.base_revision,
        torch_dtype=torch.float32,
    )
    model: Any = PeftModel.from_pretrained(base, str(checkpoint_dir))
    merged = model.merge_and_unload()
    merged_dir.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(str(merged_dir))
    processor = WhisperProcessor.from_pretrained(
        config.base_model_id, revision=config.base_revision
    )
    processor.save_pretrained(str(merged_dir))


def convert_to_ct2(merged_dir: Path, ct2_dir: Path) -> dict[str, str]:
    """Convert to CTranslate2 float32; return {filename: sha256} pins."""
    from ctranslate2.converters import TransformersConverter

    converter = TransformersConverter(
        str(merged_dir),
        copy_files=["tokenizer.json", "preprocessor_config.json"],
    )
    converter.convert(str(ct2_dir), quantization="float32", force=True)
    pins: dict[str, str] = {}
    for path in sorted(ct2_dir.iterdir()):
        if path.is_file():
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1 << 16), b""):
                    digest.update(chunk)
            pins[path.name] = digest.hexdigest()
    (ct2_dir / "artifact-pins.json").write_text(json.dumps(pins, indent=2) + "\n", encoding="utf-8")
    return pins
