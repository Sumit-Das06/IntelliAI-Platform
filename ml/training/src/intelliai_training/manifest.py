"""Frozen-manifest loading for training — torch-free.

Consumes the platform's 5-field JSONL exactly as `ml/datasets` freezes
it. The manifest hash is verified BEFORE any sample is read: training
against bytes that drifted from the pin is refused, not warned about.
The validation split is a pure function of sample id and the configured
fraction — no RNG, no order dependence.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class TrainSample(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    audio: str  # path relative to the data root
    text: str
    language: str
    duration_seconds: float


class ManifestDriftError(RuntimeError):
    """The manifest bytes do not match the pinned SHA-256."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path, *, expected_sha256: str) -> list[TrainSample]:
    """Load and pin-verify the frozen manifest; stable (file) order."""
    actual = sha256_file(path)
    if actual != expected_sha256.lower():
        msg = (
            f"training manifest {path} does not match its pin: expected "
            f"{expected_sha256.lower()}, got {actual}. A frozen manifest "
            "never changes silently — refusing to train."
        )
        raise ManifestDriftError(msg)
    samples = [
        TrainSample.model_validate(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return samples


def split_validation(
    samples: list[TrainSample], *, fraction: float
) -> tuple[list[TrainSample], list[TrainSample]]:
    """Deterministic split: a sample is validation iff the integer value
    of sha256(id) mod 10_000 falls below fraction*10_000. Pure function
    of the id — independent of order, machine, and run count."""
    if fraction <= 0:
        return list(samples), []
    threshold = int(fraction * 10_000)
    train: list[TrainSample] = []
    validation: list[TrainSample] = []
    for sample in samples:
        bucket = (
            int.from_bytes(hashlib.sha256(sample.id.encode("utf-8")).digest()[:4], "big") % 10_000
        )
        (validation if bucket < threshold else train).append(sample)
    return train, validation
