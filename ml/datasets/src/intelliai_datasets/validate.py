"""Deterministic validation: every rejection carries an explicit reason.

Nothing is silently discarded. The report is a committed artifact — the
answer to "why is sample X not in the manifest?" must survive years.
"""

from __future__ import annotations

import enum
import unicodedata
from collections.abc import Iterable, Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from intelliai_datasets.samples import CandidateSample

# Bounds match the platform's evaluation-corpus clip law (2 s minimum)
# and Whisper's 30 s window for training examples.
MIN_DURATION_SECONDS = 2.0
MAX_DURATION_SECONDS = 30.0


class RejectionReason(enum.StrEnum):
    AUDIO_MISSING = "audio_missing"
    AUDIO_UNREADABLE = "audio_unreadable"
    DURATION_TOO_SHORT = "duration_too_short"
    DURATION_TOO_LONG = "duration_too_long"
    EMPTY_TRANSCRIPT = "empty_transcript"
    WRONG_LANGUAGE = "wrong_language"
    DUPLICATE_AUDIO = "duplicate_audio"
    EVAL_CONTAMINATION = "eval_contamination"
    SPEAKER_IN_EVAL = "speaker_in_eval"


class Rejection(BaseModel):
    model_config = ConfigDict(frozen=True)

    sample_id: str
    reason: RejectionReason
    detail: str = ""


class ValidationReport(BaseModel):
    """The committed record of one validation pass."""

    model_config = ConfigDict(frozen=True)

    source: str
    language: str
    split: str
    candidates: int
    accepted: int
    rejections: tuple[Rejection, ...]
    accepted_duration_seconds: float

    @property
    def rejected(self) -> int:
        return len(self.rejections)


def normalize_text(text: str) -> str:
    """Deterministic transcript normalization for manifests: NFC + trim.

    Deliberately minimal — references are stored close to verbatim
    (pre-normalization by corpus law); scoring-time normalization is the
    evaluation plane's job and versioned there.
    """
    return unicodedata.normalize("NFC", text).strip()


def validate_samples(
    samples: Sequence[CandidateSample],
    *,
    expected_language: str,
    data_root: Path,
    eval_sha256: Iterable[str] = (),
    eval_speakers: Iterable[str] = (),
) -> tuple[list[CandidateSample], list[Rejection]]:
    """Validate in stable input order; return (accepted, rejections).

    ``eval_sha256`` / ``eval_speakers``: the frozen evaluation set's
    content hashes and speaker roster — training candidates matching
    either are rejected (contamination / speaker leakage).
    """
    frozen_hashes = {h.lower() for h in eval_sha256}
    frozen_speakers = set(eval_speakers)
    seen_hashes: set[str] = set()
    accepted: list[CandidateSample] = []
    rejections: list[Rejection] = []

    for sample in samples:
        reason = _reject_reason(
            sample,
            expected_language=expected_language,
            data_root=data_root,
            frozen_hashes=frozen_hashes,
            frozen_speakers=frozen_speakers,
            seen_hashes=seen_hashes,
        )
        if reason is None:
            seen_hashes.add(sample.sha256.lower())
            accepted.append(sample)
        else:
            rejections.append(reason)
    return accepted, rejections


def _reject_reason(
    sample: CandidateSample,
    *,
    expected_language: str,
    data_root: Path,
    frozen_hashes: set[str],
    frozen_speakers: set[str],
    seen_hashes: set[str],
) -> Rejection | None:
    target = data_root / sample.path
    if not target.exists():
        return Rejection(
            sample_id=sample.id,
            reason=RejectionReason.AUDIO_MISSING,
            detail=sample.path,
        )
    if sample.duration_seconds <= 0 or sample.sample_rate_hz <= 0:
        return Rejection(
            sample_id=sample.id,
            reason=RejectionReason.AUDIO_UNREADABLE,
            detail="probe reported no decodable audio",
        )
    if sample.duration_seconds < MIN_DURATION_SECONDS:
        return Rejection(
            sample_id=sample.id,
            reason=RejectionReason.DURATION_TOO_SHORT,
            detail=f"{sample.duration_seconds:.2f}s < {MIN_DURATION_SECONDS}s",
        )
    if sample.duration_seconds > MAX_DURATION_SECONDS:
        return Rejection(
            sample_id=sample.id,
            reason=RejectionReason.DURATION_TOO_LONG,
            detail=f"{sample.duration_seconds:.2f}s > {MAX_DURATION_SECONDS}s",
        )
    if not normalize_text(sample.text):
        return Rejection(sample_id=sample.id, reason=RejectionReason.EMPTY_TRANSCRIPT)
    if sample.language != expected_language:
        return Rejection(
            sample_id=sample.id,
            reason=RejectionReason.WRONG_LANGUAGE,
            detail=f"{sample.language!r} != {expected_language!r}",
        )
    digest = sample.sha256.lower()
    if digest in seen_hashes:
        return Rejection(
            sample_id=sample.id,
            reason=RejectionReason.DUPLICATE_AUDIO,
            detail=digest,
        )
    if digest in frozen_hashes:
        return Rejection(
            sample_id=sample.id,
            reason=RejectionReason.EVAL_CONTAMINATION,
            detail="content hash present in the frozen evaluation set",
        )
    if sample.speaker_id is not None and sample.speaker_id in frozen_speakers:
        return Rejection(
            sample_id=sample.id,
            reason=RejectionReason.SPEAKER_IN_EVAL,
            detail=sample.speaker_id,
        )
    return None
