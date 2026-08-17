"""M22: cleaning rules and no-speech negatives — deterministic, governed."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from intelliai_datasets.negatives import generate_negatives
from intelliai_datasets.samples import CandidateSample
from intelliai_datasets.sources import source
from intelliai_datasets.validate import (
    RejectionReason,
    clean_transcript,
    validate_samples,
)


def _flac(path: Path, seconds: float = 3.0, amplitude: float = 0.0) -> str:
    """A real FLAC when the audio stack is present, else a placeholder file.

    Validation checks EXISTENCE and metadata only — the placeholder is
    enough for admission tests; generation tests importorskip the stack.
    """
    import hashlib

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import numpy as np
        import soundfile
    except ModuleNotFoundError:
        path.write_bytes(b"fLaC-placeholder:" + str((seconds, amplitude)).encode())
    else:
        rng = np.random.default_rng(7)
        samples = (rng.standard_normal(int(seconds * 16000)) * amplitude).astype("float32")
        soundfile.write(str(path), samples, 16000, subtype="PCM_16", format="FLAC")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sample(root: Path, sample_id: str, **overrides: object) -> CandidateSample:
    path = root / f"{sample_id}.flac"
    digest = _flac(path, amplitude=0.1)
    values: dict[str, object] = {
        "id": sample_id,
        "source": "indicvoices",
        "language": "hi",
        "split": "train",
        "path": f"{sample_id}.flac",
        "text": "नमस्ते दुनिया",
        "duration_seconds": 3.0,
        "sample_rate_hz": 16000,
        "channels": 1,
        "sha256": digest,
        "speaker_id": "S1",
    }
    values.update(overrides)
    return CandidateSample.model_validate(values)


class TestCleaning:
    def test_control_characters_become_spaces_and_collapse(self) -> None:
        cleaned, categories = clean_transcript("एक\x00दो​  तीन")
        assert cleaned == "एक दो तीन"
        assert "control_characters_stripped" in categories
        assert "whitespace_collapsed" in categories

    def test_clean_text_passes_through_unchanged(self) -> None:
        cleaned, categories = clean_transcript("साफ़ वाक्य")
        assert cleaned == "साफ़ वाक्य"
        assert categories == ()

    def test_markup_rows_are_rejected_not_stripped(self, tmp_path: Path) -> None:
        # Stripping <unintelligible> would leave audio whose speech the
        # text omits — supervision that TEACHES deletions. Dropping is
        # the deliberate policy; the rejection record is the provenance.
        keep = _sample(tmp_path, "keep")
        drop = _sample(tmp_path, "drop", text="कुछ <unintelligible> शब्द")
        accepted, rejections = validate_samples(
            [keep, drop], expected_language="hi", data_root=tmp_path, clean_markup=True
        )
        assert [s.id for s in accepted] == ["keep"]
        assert rejections[0].reason == RejectionReason.MARKUP_IN_TRANSCRIPT
        assert "<unintelligible>" in rejections[0].detail

    def test_cleaning_is_off_by_default(self, tmp_path: Path) -> None:
        # Every pre-M22 manifest must stay byte-reproducible.
        drop = _sample(tmp_path, "markup", text="कुछ <unintelligible> शब्द")
        accepted, _ = validate_samples([drop], expected_language="hi", data_root=tmp_path)
        assert [s.id for s in accepted] == ["markup"]


class TestNoSpeechAdmission:
    def test_zxx_negative_with_empty_text_is_admitted(self, tmp_path: Path) -> None:
        negative = _sample(
            tmp_path,
            "neg",
            language="zxx",
            text="",
            speaker_id=None,
            source="negatives-synthetic",
        )
        accepted, rejections = validate_samples(
            [negative], expected_language="hi", data_root=tmp_path, allow_no_speech=True
        )
        assert [s.id for s in accepted] == ["neg"]
        assert rejections == []

    def test_zxx_with_text_is_refused(self, tmp_path: Path) -> None:
        bad = _sample(tmp_path, "bad", language="zxx", text="कुछ", speaker_id=None)
        _, rejections = validate_samples(
            [bad], expected_language="hi", data_root=tmp_path, allow_no_speech=True
        )
        assert rejections[0].reason == RejectionReason.WRONG_LANGUAGE

    def test_no_speech_is_off_by_default(self, tmp_path: Path) -> None:
        negative = _sample(tmp_path, "neg", language="zxx", text="", speaker_id=None)
        _, rejections = validate_samples([negative], expected_language="hi", data_root=tmp_path)
        assert len(rejections) == 1  # empty transcript / wrong language — refused


class TestNegativeGeneration:
    @pytest.fixture(autouse=True)
    def _needs_audio_stack(self) -> None:
        pytest.importorskip("numpy")
        pytest.importorskip("soundfile")

    def test_generation_is_deterministic_and_registered(self, tmp_path: Path) -> None:
        parent = _sample(tmp_path / "data", "parent", amplitude=0.0)
        first = generate_negatives(
            data_root=tmp_path / "data",
            out_candidates=tmp_path / "one.json",
            silence_count=2,
            noise_count=1,
            derived_count=1,
            derived_pool=[parent],
            seed=99,
        )
        second = generate_negatives(
            data_root=tmp_path / "data",
            out_candidates=tmp_path / "two.json",
            silence_count=2,
            noise_count=1,
            derived_count=1,
            derived_pool=[parent],
            seed=99,
        )
        assert [c.sha256 for c in first] == [c.sha256 for c in second]
        assert (tmp_path / "one.json").read_bytes() == (tmp_path / "two.json").read_bytes()
        assert all(c.language == "zxx" and c.text == "" for c in first)
        # Every negative source is registered — provenance can name it.
        for record in first:
            assert source(record.source).language == "zxx"
        derived = [c for c in first if c.source == "negatives-indicvoices-derived"]
        assert derived and "parent" in derived[0].notes

    def test_loud_parents_donate_nothing(self, tmp_path: Path) -> None:
        parent = _sample(tmp_path / "data", "loud", amplitude=0.2)
        produced = generate_negatives(
            data_root=tmp_path / "data",
            out_candidates=tmp_path / "out.json",
            silence_count=0,
            noise_count=0,
            derived_count=3,
            derived_pool=[parent],
            seed=1,
        )
        assert produced == []


class TestQwenNegativeRepresentation:
    def test_zxx_maps_to_the_official_none_header(self) -> None:
        from intelliai_training.manifest import TrainSample
        from intelliai_training.qwen_manifest import qwen_text

        negative = TrainSample(
            id="n", audio="n.flac", text="", language="zxx", duration_seconds=4.0
        )
        # The EXACT string the pinned base emits on silence (15E probe).
        assert qwen_text(negative, language_tag="Hindi") == "language None<asr_text>"

    def test_a_zxx_row_with_text_refuses_conversion(self) -> None:
        from intelliai_training.manifest import TrainSample
        from intelliai_training.qwen_manifest import qwen_text

        bad = TrainSample(id="b", audio="b.flac", text="कुछ", language="zxx", duration_seconds=4.0)
        with pytest.raises(ValueError, match="must be empty"):
            qwen_text(bad, language_tag="Hindi")

    def test_json_round_trip_stays_deterministic(self, tmp_path: Path) -> None:
        rows = [
            {
                "id": "a",
                "audio": "a.flac",
                "text": "नमस्ते",
                "language": "hi",
                "duration_seconds": 3.0,
            },
            {"id": "n", "audio": "n.flac", "text": "", "language": "zxx", "duration_seconds": 4.0},
        ]
        manifest = tmp_path / "m.jsonl"
        manifest.write_bytes(
            ("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n").encode("utf-8")
        )
        import hashlib

        from intelliai_training.qwen_manifest import convert_manifest

        sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
        record = convert_manifest(
            manifest,
            expected_sha256=sha,
            output_dir=tmp_path / "out",
            language_tag="Hindi",
            validation_fraction=0.0,
        )
        lines = Path(record.train_path).read_text(encoding="utf-8").splitlines()
        texts = [json.loads(line)["text"] for line in lines]
        assert texts == ["language Hindi<asr_text>नमस्ते", "language None<asr_text>"]
