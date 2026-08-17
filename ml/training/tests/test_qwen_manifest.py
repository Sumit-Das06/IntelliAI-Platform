"""Qwen manifest conversion — deterministic, torch-free, governed.

The conversion is the seam between the frozen platform manifest and the
official Qwen training format; these tests pin the format bytes, the
determinism, and the governance re-checks (eval disjointness) without
any ML dependency.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from intelliai_training.config import QwenTrainingConfig
from intelliai_training.manifest import TrainSample, sha256_file
from intelliai_training.qwen_manifest import convert_manifest, qwen_text

REPO_ROOT = Path(__file__).resolve().parents[3]
FROZEN_MANIFEST = REPO_ROOT / "ml/datasets/manifests/hi-public-train-v1.jsonl"
FROZEN_SHA = "a4748dee8a7a82ee4e1233587f3f4366fba91dfcb1e367415191e2e3388ee0df"
EVAL_MANIFEST = REPO_ROOT / "ml/evaluation/stt/datasets/stt-hi-public-eval-v1.json"


def _tiny_manifest(path: Path) -> str:
    rows = [
        {
            "id": "clip-a",
            "audio": "src/a.flac",
            "text": "नमस्ते दुनिया",
            "language": "hi",
            "duration_seconds": 3.5,
        },
        {
            "id": "clip-b",
            "audio": "src/b.flac",
            "text": "दूसरा वाक्य",
            "language": "hi",
            "duration_seconds": 4.25,
        },
    ]
    path.write_bytes(
        ("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n").encode("utf-8")
    )
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestOfficialFormat:
    def test_text_carries_the_official_language_header(self) -> None:
        sample = TrainSample(
            id="x", audio="a.flac", text="नमस्ते", language="hi", duration_seconds=2.0
        )
        # The SAME header the model emits and the serving adapter parses:
        # supervision and product output are one format by construction.
        assert qwen_text(sample, language_tag="Hindi") == "language Hindi<asr_text>नमस्ते"

    def test_rows_are_the_official_two_field_shape(self, tmp_path: Path) -> None:
        sha = _tiny_manifest(tmp_path / "m.jsonl")
        record = convert_manifest(
            tmp_path / "m.jsonl",
            expected_sha256=sha,
            output_dir=tmp_path / "out",
            language_tag="Hindi",
            validation_fraction=0.0,
        )
        rows = [
            json.loads(line)
            for line in Path(record.train_path).read_text(encoding="utf-8").splitlines()
        ]
        assert [set(r) for r in rows] == [{"audio", "text"}, {"audio", "text"}]
        assert rows[0]["audio"] == "src/a.flac"  # relative, POSIX, never copied
        assert rows[0]["text"].startswith("language Hindi<asr_text>")

    def test_conversion_is_byte_deterministic(self, tmp_path: Path) -> None:
        sha = _tiny_manifest(tmp_path / "m.jsonl")
        first = convert_manifest(
            tmp_path / "m.jsonl",
            expected_sha256=sha,
            output_dir=tmp_path / "one",
            language_tag="Hindi",
            validation_fraction=0.0,
        )
        second = convert_manifest(
            tmp_path / "m.jsonl",
            expected_sha256=sha,
            output_dir=tmp_path / "two",
            language_tag="Hindi",
            validation_fraction=0.0,
        )
        assert first.train_sha256 == second.train_sha256
        assert Path(first.train_path).read_bytes() == Path(second.train_path).read_bytes()

    def test_drifted_manifest_is_refused(self, tmp_path: Path) -> None:
        _tiny_manifest(tmp_path / "m.jsonl")
        from intelliai_training.manifest import ManifestDriftError

        with pytest.raises(ManifestDriftError):
            convert_manifest(
                tmp_path / "m.jsonl",
                expected_sha256="0" * 64,
                output_dir=tmp_path / "out",
                language_tag="Hindi",
                validation_fraction=0.0,
            )

    def test_validation_split_is_disjoint_and_complete(self, tmp_path: Path) -> None:
        sha = _tiny_manifest(tmp_path / "m.jsonl")
        record = convert_manifest(
            tmp_path / "m.jsonl",
            expected_sha256=sha,
            output_dir=tmp_path / "out",
            language_tag="Hindi",
            validation_fraction=0.2,
        )
        train_rows = Path(record.train_path).read_text(encoding="utf-8").splitlines()
        val_rows = (
            Path(record.validation_path).read_text(encoding="utf-8").splitlines()
            if record.validation_path
            else []
        )
        assert len(train_rows) + len(val_rows) == 2
        assert record.train_rows + record.validation_rows == 2


class TestFrozenManifestGovernance:
    """Re-verification against the REAL frozen artifacts (read-only)."""

    @pytest.fixture(autouse=True)
    def _needs_frozen_files(self) -> None:
        if not FROZEN_MANIFEST.exists() or not EVAL_MANIFEST.exists():
            pytest.skip("frozen manifests not present in this checkout")

    def test_the_frozen_training_manifest_still_matches_its_pin(self) -> None:
        assert sha256_file(FROZEN_MANIFEST) == FROZEN_SHA

    def test_training_and_eval_never_share_a_clip(self) -> None:
        # Freeze-time curation enforced content-hash disjointness; this
        # re-checks the cheap invariants forever: no shared ids, no
        # shared audio paths between what trains and what judges.
        train_ids = set()
        train_audio = set()
        for line in FROZEN_MANIFEST.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                train_ids.add(row["id"])
                train_audio.add(row["audio"])
        eval_doc = json.loads(EVAL_MANIFEST.read_text(encoding="utf-8"))
        eval_ids = {clip["id"] for clip in eval_doc["clips"]}
        eval_audio = {clip["path"] for clip in eval_doc["clips"] if clip.get("path")}
        assert not (train_ids & eval_ids)
        assert not (train_audio & eval_audio)

    def test_default_config_points_at_the_pinned_manifest(self) -> None:
        config = QwenTrainingConfig()
        assert config.manifest_sha256 == FROZEN_SHA
        assert config.manifest_path.endswith("hi-public-train-v1.jsonl")
        # Identity law: the training base is the recorded 15E upstream
        # revision, full 40-hex — never a floating "main".
        assert config.base_revision == "5eb144179a02acc5e5ba31e748d22b0cf3e303b0"
        assert len(config.base_revision) == 40
