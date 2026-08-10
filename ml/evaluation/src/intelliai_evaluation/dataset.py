"""Evaluation dataset manifests — versioned, immutable, audio-never-committed.

A dataset is a manifest: pinned sources + verification hashes + reference
texts. The audio itself is materialized on demand (fetch module) into a
gitignored data directory — the same weights-out-of-git discipline the
platform applies to models (large-file guard; AI_STRATEGY §2 versioning).
Released manifests are immutable; changes create the next version.
"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from intelliai_runtime_contract import Capability


class SyntheticSpec(BaseModel):
    """Deterministically generated audio — probes that need no download."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["silence", "tone"]
    duration_seconds: float
    sample_rate_hz: int = 16000
    frequency_hz: float = 440.0  # tone only; ignored for silence


class EvalClip(BaseModel):
    """One clip: exactly one source (pinned URL, local path, or synthetic spec).

    A ``path`` source is a file that already exists on the machine —
    ingested public data or self-recorded audio — relative to the data
    directory the run materializes into. Local files carry the same
    SHA-256 pin as downloads: the hash is the identity, and a path clip
    that does not match its pin is refused exactly like a bad download.
    Audio is never committed; only the manifest (path + pin) is.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    language: str  # BCP-47-ish; "zxx" = no linguistic content (probes)
    reference_text: str  # "" means: correct output is NO transcription
    duration_seconds: float
    license: str
    url: str | None = None
    path: str | None = None  # relative to the run's data directory
    sha256: str | None = None
    synthetic: SyntheticSpec | None = None
    notes: str = ""

    @model_validator(mode="after")
    def _exactly_one_source(self) -> EvalClip:
        sources = sum(x is not None for x in (self.url, self.path, self.synthetic))
        if sources != 1:
            msg = f"clip {self.id!r}: exactly one of url/path/synthetic is required"
            raise ValueError(msg)
        if self.url is not None and self.sha256 is None:
            msg = f"clip {self.id!r}: url clips require a sha256 pin"
            raise ValueError(msg)
        if self.path is not None:
            if self.sha256 is None:
                msg = f"clip {self.id!r}: path clips require a sha256 pin"
                raise ValueError(msg)
            # Judged under BOTH path flavors, so a manifest means the same
            # thing on every machine: "C:/x" must be refused on Linux CI
            # exactly as it is on a Windows workstation.
            as_windows = PureWindowsPath(self.path)
            as_posix = PurePosixPath(self.path)
            escapes = (
                as_windows.is_absolute()
                or as_posix.is_absolute()
                or as_windows.drive != ""
                or ".." in as_windows.parts
                or ".." in as_posix.parts
            )
            if escapes:
                msg = (
                    f"clip {self.id!r}: path must be relative to the data "
                    "directory and must not escape it"
                )
                raise ValueError(msg)
        return self

    @property
    def filename(self) -> str:
        if self.url is not None:
            suffix = Path(self.url).suffix or ".bin"
            return f"{self.id}{suffix}"
        if self.path is not None:
            return self.path
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


def find_dataset(directory: Path, name: str, version: int) -> EvalDataset:
    """Locate a dataset by its IDENTITY, never by its filename.

    Evidence records cite ``name@vN`` — the same discipline that makes
    baselines cite names rather than paths. A file can be renamed or
    moved; a released (name, version) pair cannot change, so reproducing
    a years-old measurement must not depend on where someone put the
    file. Every manifest in the directory is read and matched.
    """
    for path in sorted(directory.glob("*.json")):
        candidate = load_dataset(path)
        if candidate.name == name and candidate.version == version:
            return candidate
    msg = f"no dataset {name}@v{version} under {directory}"
    raise FileNotFoundError(msg)
