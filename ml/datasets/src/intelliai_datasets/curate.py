"""Deterministic curation: stable content-hash order, duration budget.

The selection is a pure function of the accepted sample set and the
budget — independent of download order, filesystem order, and machine.
Content-hash ordering is the platform's identity discipline ("the hash
is the identity") applied to selection: reproducible, and free of the
human bias a hand-picked subset would carry.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from intelliai_datasets.samples import CandidateSample


def curate_by_budget(
    samples: Sequence[CandidateSample],
    *,
    target_duration_seconds: float,
) -> list[CandidateSample]:
    """Select samples in ascending sha256 order until the budget is met.

    The first sample that crosses the budget is INCLUDED (the target is
    a floor for "approximately N hours", not a hard ceiling), then
    selection stops. A non-positive budget selects everything.
    """
    ordered = sorted(samples, key=lambda s: s.sha256.lower())
    if target_duration_seconds <= 0:
        return ordered
    selected: list[CandidateSample] = []
    total = 0.0
    for sample in ordered:
        selected.append(sample)
        total += sample.duration_seconds
        if total >= target_duration_seconds:
            break
    return selected


def curate_count(
    samples: Sequence[CandidateSample],
    *,
    count: int,
) -> list[CandidateSample]:
    """Select the first ``count`` samples in ascending sha256 order."""
    ordered = sorted(samples, key=lambda s: s.sha256.lower())
    return ordered[: max(count, 0)]


def total_duration(samples: Sequence[CandidateSample]) -> float:
    return sum(s.duration_seconds for s in samples)


def curate_speakers(
    samples: Sequence[CandidateSample],
    *,
    target_clips: int,
    max_per_speaker: int,
) -> list[CandidateSample]:
    """Whole-speaker selection: the unit of choice is a SPEAKER, not a clip.

    Speakers are taken in ascending order of sha256(speaker_id) — stable,
    content-independent, bias-free — and each contributes at most
    ``max_per_speaker`` clips (its clips ordered by their own sha256).
    Selection stops once ``target_clips`` is reached; the crossing
    speaker's clips are included whole (up to the cap), so the roster is
    always a set of complete speaker contributions, never a split one.

    Every selected sample is guaranteed to carry a speaker id: samples
    without one cannot join a speaker-disjoint set by definition and are
    refused loudly here rather than silently dropped (validation should
    have rejected them first).
    """
    missing = [s.id for s in samples if s.speaker_id is None]
    if missing:
        msg = (
            f"{len(missing)} sample(s) without speaker_id cannot enter a "
            f"speaker-curated set (first: {missing[0]!r}); reject them in "
            "validation first"
        )
        raise ValueError(msg)

    def speaker_key(speaker: str) -> str:
        return hashlib.sha256(speaker.encode("utf-8")).hexdigest()

    by_speaker: dict[str, list[CandidateSample]] = {}
    for sample in samples:
        assert sample.speaker_id is not None  # noqa: S101 — guarded above
        by_speaker.setdefault(sample.speaker_id, []).append(sample)

    selected: list[CandidateSample] = []
    for speaker in sorted(by_speaker, key=speaker_key):
        clips = sorted(by_speaker[speaker], key=lambda s: s.sha256.lower())
        selected.extend(clips[:max_per_speaker])
        if len(selected) >= target_clips:
            break
    return selected


def speaker_roster(samples: Sequence[CandidateSample]) -> tuple[str, ...]:
    """The sorted, deduplicated speaker ids of a selection."""
    return tuple(sorted({s.speaker_id for s in samples if s.speaker_id is not None}))
