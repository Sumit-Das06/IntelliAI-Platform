"""The shipped manifest must validate, and the schema must refuse ambiguity."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from intelliai_evaluation.dataset import EvalClip, load_dataset

MANIFEST = Path(__file__).parents[1] / "stt" / "datasets" / "stt-eval-v1.json"


class TestShippedManifest:
    def test_v1_manifest_is_valid(self) -> None:
        dataset = load_dataset(MANIFEST)
        assert dataset.name == "stt-eval-seed"
        assert dataset.version == 1
        assert dataset.capability == "transcription"
        assert len(dataset.clips) == 4

    def test_url_clips_are_pinned(self) -> None:
        dataset = load_dataset(MANIFEST)
        for clip in dataset.clips:
            if clip.url is not None:
                assert clip.sha256 is not None
                assert len(clip.sha256) == 64

    def test_probe_clips_expect_silence(self) -> None:
        dataset = load_dataset(MANIFEST)
        probes = [c for c in dataset.clips if c.synthetic is not None]
        assert len(probes) == 2
        assert all(c.reference_text == "" for c in probes)
        assert all(c.language == "zxx" for c in probes)


class TestSchemaRefusals:
    def _clip(self, **overrides: object) -> dict[str, object]:
        base: dict[str, object] = {
            "id": "x",
            "language": "en",
            "reference_text": "hi",
            "duration_seconds": 1.0,
            "license": "test",
        }
        base.update(overrides)
        return base

    def test_clip_with_no_source_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="exactly one"):
            EvalClip.model_validate(self._clip())

    def test_clip_with_both_sources_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="exactly one"):
            EvalClip.model_validate(
                self._clip(
                    url="https://example.com/a.wav",
                    sha256="0" * 64,
                    synthetic={"kind": "silence", "duration_seconds": 1.0},
                )
            )

    def test_url_clip_without_sha256_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="sha256"):
            EvalClip.model_validate(self._clip(url="https://example.com/a.wav"))

    def test_filename_derivation(self) -> None:
        url_clip = EvalClip.model_validate(
            self._clip(url="https://example.com/audio/a.flac", sha256="0" * 64)
        )
        assert url_clip.filename == "x.flac"
        synth = EvalClip.model_validate(
            self._clip(synthetic={"kind": "silence", "duration_seconds": 1.0})
        )
        assert synth.filename == "x.wav"


class TestPathSource:
    """Local-path clips: same pin discipline as downloads."""

    def _clip(self, **overrides: object) -> dict[str, object]:
        base: dict[str, object] = {
            "id": "p",
            "language": "hi",
            "reference_text": "नमस्ते",
            "duration_seconds": 2.0,
            "license": "CC-BY-4.0",
        }
        base.update(overrides)
        return base

    def test_path_clip_is_valid_with_pin(self) -> None:
        clip = EvalClip.model_validate(self._clip(path="hi/fleurs/000123.wav", sha256="0" * 64))
        assert clip.filename == "hi/fleurs/000123.wav"

    def test_path_clip_without_sha256_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="sha256 pin"):
            EvalClip.model_validate(self._clip(path="a.wav"))

    def test_absolute_path_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="relative"):
            EvalClip.model_validate(self._clip(path="C:/audio/a.wav", sha256="0" * 64))

    def test_escaping_path_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="escape"):
            EvalClip.model_validate(self._clip(path="../a.wav", sha256="0" * 64))

    def test_path_plus_url_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="exactly one"):
            EvalClip.model_validate(
                self._clip(
                    path="a.wav",
                    url="https://example.com/a.wav",
                    sha256="0" * 64,
                )
            )
