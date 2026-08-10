"""Materialize evaluation clips: pinned downloads + deterministic synthesis.

Every remote clip is verified against its manifest SHA-256 — a mismatch is
a hard failure, never a warning (the same hash-verification rule the
ModelManager applies to weights). Synthetic clips are generated with the
stdlib only, byte-deterministically: the same spec always produces the
same file on every machine.
"""

from __future__ import annotations

import hashlib
import math
import wave
from collections.abc import Iterable
from pathlib import Path

import httpx

from intelliai_evaluation.dataset import EvalClip, EvalDataset, SyntheticSpec

_DOWNLOAD_TIMEOUT_SECONDS = 60.0
_AMPLITUDE = 0.3  # tone loudness, well clear of clipping


class ClipIntegrityError(RuntimeError):
    """A materialized clip does not match its manifest pin."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate_synthetic(spec: SyntheticSpec, target: Path) -> None:
    """Write a mono 16-bit PCM WAV for the spec, deterministically."""
    frame_count = round(spec.duration_seconds * spec.sample_rate_hz)
    if spec.kind == "silence":
        frames = b"\x00\x00" * frame_count
    else:  # tone
        scale = int(_AMPLITUDE * 32767)
        step = 2.0 * math.pi * spec.frequency_hz / spec.sample_rate_hz
        frames = b"".join(
            int(scale * math.sin(step * n)).to_bytes(2, "little", signed=True)
            for n in range(frame_count)
        )
    with wave.open(str(target), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(spec.sample_rate_hz)
        writer.writeframes(frames)


def materialize_clip(clip: EvalClip, data_dir: Path, client: httpx.Client) -> Path:
    """Ensure the clip exists locally and matches its pin; return its path."""
    target = data_dir / clip.filename

    if clip.synthetic is not None:
        if not target.exists():
            generate_synthetic(clip.synthetic, target)
        return target

    if clip.path is not None:
        # A path clip is never downloaded: it was placed by ingestion (or a
        # recording pipeline) before the run. Missing or mismatched is a
        # hard failure — materialization verifies identity, it does not
        # create it.
        if clip.sha256 is None:  # unreachable: model validator guarantees
            msg = f"clip {clip.id!r}: path clip without sha256 pin"
            raise ClipIntegrityError(msg)
        if not target.exists():
            msg = (
                f"clip {clip.id!r}: local file {target} does not exist; "
                "run the ingestion that produced this manifest first"
            )
            raise ClipIntegrityError(msg)
        actual = sha256_file(target)
        if actual != clip.sha256.lower():
            msg = (
                f"clip {clip.id!r}: SHA-256 mismatch — expected "
                f"{clip.sha256.lower()}, got {actual}; refusing to score "
                "unverified audio"
            )
            raise ClipIntegrityError(msg)
        return target

    if clip.url is None or clip.sha256 is None:  # unreachable: model validator guarantees
        msg = f"clip {clip.id!r}: url clip without url/sha256 pin"
        raise ClipIntegrityError(msg)
    if target.exists() and sha256_file(target) == clip.sha256.lower():
        return target

    response = client.get(clip.url)
    response.raise_for_status()
    target.write_bytes(response.content)

    actual = sha256_file(target)
    if actual != clip.sha256.lower():
        target.unlink(missing_ok=True)
        msg = (
            f"clip {clip.id!r}: SHA-256 mismatch — expected {clip.sha256.lower()}, "
            f"got {actual}; refusing to keep unverified audio"
        )
        raise ClipIntegrityError(msg)
    return target


def materialize_clips(clips: Iterable[EvalClip], data_dir: Path) -> dict[str, Path]:
    """Materialize exactly these clips; return id → local path.

    Slice-level on purpose: a session measures one language slice, and a
    `hi` session has no business downloading English audio it will never
    send (found at B7 — the whole-dataset call made every session pay for
    every clip).
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    with httpx.Client(follow_redirects=True, timeout=_DOWNLOAD_TIMEOUT_SECONDS) as client:
        for clip in clips:
            paths[clip.id] = materialize_clip(clip, data_dir, client)
    return paths


def materialize(dataset: EvalDataset, data_dir: Path) -> dict[str, Path]:
    """Materialize every clip in the dataset; return id → local path."""
    return materialize_clips(dataset.clips, data_dir)
