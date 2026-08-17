"""Frozen platform manifest -> official Qwen3-ASR training JSONL.

The official fine-tuning script (QwenLM/Qwen3-ASR/finetuning) consumes
rows of the shape

    {"audio": "<path>", "text": "language Hindi<asr_text><transcript>"}

— the SAME ``language <Name><asr_text>`` header our serving adapter
parses, so the fine-tune's supervision and the product's parse are one
format by construction.

Rules, all deterministic:

- The 5-field platform manifest is pin-verified BEFORE conversion
  (``load_manifest`` refuses drift), and the validation split is the
  same pure id-hash function every experiment uses.
- Audio is REFERENCED in place, relative POSIX paths under the data
  root — nothing is copied, moved, or re-encoded. Training runs from
  the repository root exactly like evaluation does.
- Output rows preserve manifest order (train) / split order (val);
  LF endings; UTF-8 with Devanagari kept literal. Identical inputs
  produce byte-identical JSONL, and the recorded SHA-256 proves it.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from intelliai_training.manifest import (
    TrainSample,
    load_manifest,
    sha256_file,
    split_validation,
)


class QwenJsonlRecord(BaseModel):
    """What the conversion produced, for the run record."""

    model_config = ConfigDict(frozen=True)

    train_path: str
    train_sha256: str
    train_rows: int
    validation_path: str | None
    validation_sha256: str | None
    validation_rows: int
    source_manifest_sha256: str
    total_duration_seconds: float


#: Manifest language codes -> the official emission header names. "zxx"
#: (no linguistic content — the M22 negatives) maps to "None", which is
#: LITERALLY what the pinned base model emits on silence (15E probe
#: evidence, pinned by the serving adapter's parser tests).
_LANGUAGE_HEADERS = {"hi": "Hindi", "en": "English", "zh": "Chinese", "zxx": "None"}


def qwen_text(sample: TrainSample, *, language_tag: str) -> str:
    """The official supervision string for one sample.

    ``language_tag`` names the DEFAULT header (the corpus language);
    a sample whose own language differs — the zxx negatives — takes its
    own mapped header. A zxx negative must carry an empty transcript,
    so its full target is exactly ``language None<asr_text>``.
    """
    header = language_tag
    if sample.language in _LANGUAGE_HEADERS and _LANGUAGE_HEADERS[sample.language] != header:
        header = _LANGUAGE_HEADERS[sample.language]
    if sample.language == "zxx" and sample.text.strip():
        msg = f"negative {sample.id} carries text; a zxx row must be empty"
        raise ValueError(msg)
    return f"language {header}<asr_text>{sample.text}"


def _write_jsonl(samples: list[TrainSample], path: Path, *, language_tag: str) -> str:
    lines = [
        json.dumps(
            {
                "audio": Path(sample.audio).as_posix(),
                "text": qwen_text(sample, language_tag=language_tag),
            },
            ensure_ascii=False,
        )
        for sample in samples
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    return sha256_file(path)


def convert_manifest(
    manifest_path: Path,
    *,
    expected_sha256: str,
    output_dir: Path,
    language_tag: str,
    validation_fraction: float,
) -> QwenJsonlRecord:
    """Pin-verified conversion; audio paths stay RELATIVE to the data root.

    The trainer resolves them against its configured ``data_root`` at
    load time — the derived file is machine-independent, so its SHA-256
    means the same thing on every machine.
    """
    samples = load_manifest(manifest_path, expected_sha256=expected_sha256)
    train, validation = split_validation(samples, fraction=validation_fraction)

    train_path = output_dir / "qwen-train.jsonl"
    train_sha = _write_jsonl(train, train_path, language_tag=language_tag)

    validation_path: Path | None = None
    validation_sha: str | None = None
    if validation:
        validation_path = output_dir / "qwen-validation.jsonl"
        validation_sha = _write_jsonl(validation, validation_path, language_tag=language_tag)

    return QwenJsonlRecord(
        train_path=train_path.as_posix(),
        train_sha256=train_sha,
        train_rows=len(train),
        validation_path=validation_path.as_posix() if validation_path else None,
        validation_sha256=validation_sha,
        validation_rows=len(validation),
        source_manifest_sha256=expected_sha256.lower(),
        total_duration_seconds=round(sum(s.duration_seconds for s in samples), 3),
    )
