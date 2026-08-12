"""Torch-free training-plane guarantees: pins, drift refusal, split purity."""

import json
from pathlib import Path

import pytest

from intelliai_training.config import TrainingConfig
from intelliai_training.manifest import (
    ManifestDriftError,
    load_manifest,
    sha256_file,
    split_validation,
)


def write_manifest(path: Path, count: int = 20) -> str:
    lines = [
        json.dumps(
            {
                "id": f"s-{i:03d}",
                "audio": f"a/{i}.flac",
                "text": f"नमूना {i}",
                "language": "hi",
                "duration_seconds": 4.0 + i * 0.1,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        for i in range(count)
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return sha256_file(path)


class TestManifestPin:
    def test_loads_when_pin_matches(self, tmp_path: Path) -> None:
        manifest = tmp_path / "train.jsonl"
        pin = write_manifest(manifest)
        samples = load_manifest(manifest, expected_sha256=pin)
        assert len(samples) == 20
        assert samples[0].language == "hi"

    def test_drift_is_refused_not_warned(self, tmp_path: Path) -> None:
        manifest = tmp_path / "train.jsonl"
        pin = write_manifest(manifest)
        manifest.write_text(
            manifest.read_text(encoding="utf-8").replace("नमूना 0", "बदला 0"),
            encoding="utf-8",
        )
        with pytest.raises(ManifestDriftError, match="never changes silently"):
            load_manifest(manifest, expected_sha256=pin)


class TestValidationSplit:
    def test_split_is_a_pure_function_of_ids(self, tmp_path: Path) -> None:
        manifest = tmp_path / "train.jsonl"
        pin = write_manifest(manifest, count=200)
        samples = load_manifest(manifest, expected_sha256=pin)
        first_train, first_val = split_validation(samples, fraction=0.05)
        second_train, second_val = split_validation(list(reversed(samples)), fraction=0.05)
        assert {s.id for s in first_val} == {s.id for s in second_val}
        assert {s.id for s in first_train} == {s.id for s in second_train}
        assert len(first_val) + len(first_train) == 200

    def test_zero_fraction_holds_nothing_out(self, tmp_path: Path) -> None:
        manifest = tmp_path / "t.jsonl"
        pin = write_manifest(manifest, count=10)
        samples = load_manifest(manifest, expected_sha256=pin)
        train, val = split_validation(samples, fraction=0.0)
        assert len(train) == 10
        assert val == []


class TestConfig:
    def test_config_is_frozen_and_serializable(self, tmp_path: Path) -> None:
        config = TrainingConfig(
            base_revision="abc123",
            manifest_path="m.jsonl",
            manifest_sha256="0" * 64,
        )
        restored = TrainingConfig.model_validate_json(config.model_dump_json())
        assert restored == config
        assert restored.lora.rank == 32
        assert restored.precision == "bf16"

    def test_run_record_carries_the_validation_history(self) -> None:
        # E1 learned overfitting post-hoc because validation ran once, at
        # the end. The record now carries the per-checkpoint curve, so
        # best-checkpoint selection is read off evidence, not guessed.
        from intelliai_training.config import RunRecord

        config = TrainingConfig(
            experiment="e1b-hi-lora",
            base_revision="abc123",
            manifest_path="m.jsonl",
            manifest_sha256="0" * 64,
        )
        record = RunRecord(
            experiment=config.experiment,
            run_at="2026-08-12T00:00:00+00:00",
            git_commit="deadbeef",
            config=config,
            environment={"gpu": "test"},
            train_samples=100,
            validation_samples=5,
            train_duration_seconds=1.0,
            steps_completed=300,
            final_train_loss=0.5,
            validation_loss=0.4,
            validation_history=((100, 0.6), (200, 0.45), (300, 0.4)),
            peak_vram_mib=1000.0,
            checkpoint_dir="weights/x/checkpoint-300",
            checkpoint_sha256="1" * 64,
        )
        restored = RunRecord.model_validate_json(record.model_dump_json())
        assert restored.validation_history == ((100, 0.6), (200, 0.45), (300, 0.4))
        assert restored.experiment == "e1b-hi-lora"
        # Old records (no history) still parse: the field defaults empty.
        old = json.loads(record.model_dump_json())
        del old["validation_history"]
        assert RunRecord.model_validate(old).validation_history == ()

    def test_cli_maps_the_conservative_recipe_into_the_config(self, tmp_path: Path) -> None:
        from intelliai_training.__main__ import _config_from_args

        manifest = tmp_path / "train.jsonl"
        write_manifest(manifest)
        import argparse

        args = argparse.Namespace(
            experiment="e1b-hi-lora",
            base_revision="abc123",
            manifest=str(manifest),
            manifest_sha=None,
            max_steps=600,
            batch_size=8,
            grad_accum=4,
            learning_rate=1e-4,
            warmup_steps=60,
            checkpoint_every=100,
            output_dir="weights/e1b-hi-lora",
            seed=20260811,
        )
        config = _config_from_args(args)
        assert config.experiment == "e1b-hi-lora"
        assert config.learning_rate == 1e-4
        assert config.warmup_steps == 60
        assert config.checkpoint_every_steps == 100
        assert config.max_steps == 600

    def test_trainer_module_imports_without_torch_extra(self) -> None:
        # The lazy-import contract: importing the module must never pull
        # the heavy stack. (In an env WITH the extra this still passes —
        # the assertion is that import succeeds, not that torch is absent.)
        import intelliai_training.audio_io
        import intelliai_training.merge
        import intelliai_training.trainer

        assert intelliai_training.trainer.run is not None
        assert intelliai_training.merge.merge_adapter is not None
        assert intelliai_training.audio_io.CANONICAL_RATE == 16000
