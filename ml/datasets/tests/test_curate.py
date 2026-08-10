"""Curation is a pure function of (samples, budget) — order-independent."""

from intelliai_datasets.curate import curate_by_budget, curate_count, total_duration
from intelliai_datasets.samples import CandidateSample


def sample(sample_id: str, sha: str, duration: float) -> CandidateSample:
    return CandidateSample(
        id=sample_id,
        source="fleurs",
        language="hi",
        split="train",
        path=f"{sample_id}.wav",
        text="पाठ",
        duration_seconds=duration,
        sample_rate_hz=16000,
        channels=1,
        sha256=sha.ljust(64, "0"),
    )


class TestCuration:
    def test_selection_is_input_order_independent(self) -> None:
        a = sample("a", "aa", 10.0)
        b = sample("b", "bb", 10.0)
        c = sample("c", "cc", 10.0)
        forward = curate_by_budget([a, b, c], target_duration_seconds=15.0)
        backward = curate_by_budget([c, b, a], target_duration_seconds=15.0)
        assert forward == backward

    def test_budget_floor_includes_crossing_sample(self) -> None:
        chosen = curate_by_budget(
            [sample("a", "aa", 10.0), sample("b", "bb", 10.0), sample("c", "cc", 10.0)],
            target_duration_seconds=15.0,
        )
        assert [s.id for s in chosen] == ["a", "b"]
        assert total_duration(chosen) == 20.0

    def test_nonpositive_budget_selects_everything(self) -> None:
        everything = curate_by_budget(
            [sample("a", "aa", 1.0), sample("b", "bb", 1.0)],
            target_duration_seconds=0.0,
        )
        assert len(everything) == 2

    def test_count_selection_is_hash_ordered(self) -> None:
        chosen = curate_count([sample("late", "ff", 1.0), sample("early", "11", 1.0)], count=1)
        assert [s.id for s in chosen] == ["early"]
