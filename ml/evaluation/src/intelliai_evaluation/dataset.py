"""Evaluation dataset manifests — versioned, immutable, audio-never-committed.

A dataset is a manifest: pinned sources + verification hashes + reference
texts. The audio itself is materialized on demand (fetch module) into a
gitignored data directory — the same weights-out-of-git discipline the
platform applies to models (large-file guard; AI_STRATEGY §2 versioning).
Released manifests are immutable; changes create the next version.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

# One-step debt (recorded in the module charter): replaced by the frozen
# capability enum from packages/runtime-contract in M2 step 1.
Capability = Literal["transcription"]


class SyntheticSpec(BaseModel):
    """Deterministically generated audio — probes that need no download."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["silence", "tone"]
    duration_seconds: float
    sample_rate_hz: int = 16000
    frequency_hz: float = 440.0  # tone only; ignored for silence


class EvalClip(BaseModel):
    """One clip: exactly one source (pinned URL or synthetic spec)."""

    model_config = ConfigDict(frozen=True)

    id: str
    language: str  # BCP-47-ish; "zxx" = no linguistic content (probes)
    reference_text: str  # "" means: correct output is NO transcription
    duration_seconds: float
    license: str
    url: str | None = None
    sha256: str | None = None
    synthetic: SyntheticSpec | None = None
    notes: str = ""

    @model_validator(mode="after")
    def _exactly_one_source(self) -> EvalClip:
        if (self.url is None) == (self.synthetic is None):
            msg = f"clip {self.id!r}: exactly one of url/synthetic is required"
            raise ValueError(msg)
        if self.url is not None and self.sha256 is None:
            msg = f"clip {self.id!r}: url clips require a sha256 pin"
            raise ValueError(msg)
        return self

    @property
    def filename(self) -> str:
        if self.url is not None:
            suffix = Path(self.url).suffix or ".bin"
            return f"{self.id}{suffix}"
        return f"{self.id}.wav"


class EvalDataset(BaseModel):
    """A versioned, immutable set of clips for one capability."""

    model_config = ConfigDict(frozen=True)

    name: str
    version: int
    capability: Capability
    description: str = ""
    clips: list[EvalClip]

    @model_validator(mode="after")
    def _unique_ids(self) -> EvalDataset:
        ids = [clip.id for clip in self.clips]
        if len(ids) != len(set(ids)):
            msg = f"dataset {self.name!r}: clip ids must be unique"
            raise ValueError(msg)
        return self


def load_dataset(path: Path) -> EvalDataset:
    """Load and validate a dataset manifest from JSON."""
    return EvalDataset.model_validate(json.loads(path.read_text(encoding="utf-8")))
