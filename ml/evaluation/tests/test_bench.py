"""Benchmark harness: the deterministic pieces that make runs comparable."""

import pytest

from intelliai_evaluation.bench import LevelResult, RequestSample, _to_mib, nearest_rank


class TestNearestRank:
    def test_is_deterministic_nearest_rank_no_interpolation(self) -> None:
        sample = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        assert nearest_rank(sample, 0.50) == 50.0
        assert nearest_rank(sample, 0.95) == 100.0
        assert nearest_rank(sample, 0.10) == 10.0

    def test_single_sample(self) -> None:
        assert nearest_rank([42.0], 0.95) == 42.0

    def test_empty_sample_refuses(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            nearest_rank([], 0.5)


class TestUnits:
    def test_docker_memory_units(self) -> None:
        assert _to_mib("512MiB") == 512.0
        assert _to_mib("1.5GiB") == 1536.0
        assert _to_mib("2048KiB") == 2.0


class TestModels:
    def test_request_sample_and_level_serialize(self) -> None:
        level = LevelResult(
            concurrency=5,
            requests=25,
            succeeded=20,
            overloaded=5,
            other_errors=0,
            wall_seconds=30.0,
            p50_ms=1500.0,
            p95_ms=2500.0,
            throughput_rps=0.66,
            mean_rtf=0.2,
        )
        assert LevelResult.model_validate_json(level.model_dump_json()) == level
        sample = RequestSample(ok=False, status=503, client_ms=12.0)
        assert sample.stages_ms == {}
