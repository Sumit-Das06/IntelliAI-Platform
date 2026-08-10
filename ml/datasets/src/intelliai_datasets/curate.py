"""Deterministic curation: stable content-hash order, duration budget.

The selection is a pure function of the accepted sample set and the
budget — independent of download order, filesystem order, and machine.
Content-hash ordering is the platform's identity discipline ("the hash
is the identity") applied to selection: reproducible, and free of the
human bias a hand-picked subset would carry.
"""

from __future__ import annotations

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
