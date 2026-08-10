"""Manifests are byte-deterministic and round-trip through the eval schema."""

from pathlib import Path

from intelliai_datasets.manifests import (
    HI_PROBES,
    build_eval_dataset,
    write_eval_dataset,
    write_train_jsonl,
)
from intelliai_datasets.samples import CandidateSample
from intelliai_evaluation.dataset import load_dataset


def sample(sample_id: str, sha: str) -> CandidateSample:
    return CandidateSample(
        id=sample_id,
        source="fleurs",
        language="hi",
        split="test",
        path=f"fleurs/hi_in/test/{sample_id}.wav",
        text="नमस्ते दुनिया",
        duration_seconds=4.2,
        sample_rate_hz=16000,
        channels=1,
        sha256=sha.ljust(64, "0"),
        license="CC-BY-4.0",
    )


class TestTrainJsonl:
    def test_bytes_are_deterministic_and_id_ordered(self, tmp_path: Path) -> None:
        first = tmp_path / "a.jsonl"
        second = tmp_path / "b.jsonl"
        pin_a = write_train_jsonl([sample("b2", "bb"), sample("a1", "aa")], first)
        pin_b = write_train_jsonl([sample("a1", "aa"), sample("b2", "bb")], second)
        assert pin_a.sha256 == pin_b.sha256
        lines = first.read_text(encoding="utf-8").splitlines()
        assert [line.split('"')[3] for line in lines] == ["a1", "b2"]

    def test_line_schema_is_the_platform_five_fields(self, tmp_path: Path) -> None:
        import json

        target = tmp_path / "t.jsonl"
        write_train_jsonl([sample("a1", "aa")], target)
        line = json.loads(target.read_text(encoding="utf-8").splitlines()[0])
        assert list(line.keys()) == ["id", "audio", "text", "language", "duration_seconds"]

    def test_pin_counts_and_duration(self, tmp_path: Path) -> None:
        pin = write_train_jsonl([sample("a1", "aa"), sample("b2", "bb")], tmp_path / "t.jsonl")
        assert pin.samples == 2
        assert pin.duration_seconds == 8.4


class TestEvalManifest:
    def test_round_trips_through_the_evaluation_schema(self, tmp_path: Path) -> None:
        dataset = build_eval_dataset(
            [sample("clip-b", "bb"), sample("clip-a", "aa")],
            name="stt-hi-test-eval",
            version=1,
            description="test",
            probes=HI_PROBES,
        )
        target = tmp_path / "eval.json"
        write_eval_dataset(dataset, target)
        loaded = load_dataset(target)
        assert loaded.name == "stt-hi-test-eval"
        assert [c.id for c in loaded.clips[:2]] == ["clip-a", "clip-b"]
        assert all(c.path is not None for c in loaded.clips[:2])
        assert all(c.synthetic is not None for c in loaded.clips[2:])

    def test_natural_duration_excludes_probes(self, tmp_path: Path) -> None:
        dataset = build_eval_dataset(
            [sample("clip-a", "aa")],
            name="d",
            version=1,
            description="",
            probes=HI_PROBES,
        )
        pin = write_eval_dataset(dataset, tmp_path / "d.json")
        assert pin.samples == 3
        assert pin.duration_seconds == 4.2

    def test_probe_specs_match_seed_v2_byte_identity(self) -> None:
        silence, tone = HI_PROBES
        assert silence.synthetic is not None and tone.synthetic is not None
        assert silence.synthetic.kind == "silence"
        assert silence.synthetic.duration_seconds == 10.0
        assert silence.synthetic.sample_rate_hz == 16000
        assert tone.synthetic.kind == "tone"
        assert tone.synthetic.duration_seconds == 5.0
        assert tone.synthetic.frequency_hz == 440.0
