"""Every rejection carries a reason; nothing is silently discarded."""

from pathlib import Path

from intelliai_datasets.samples import CandidateSample
from intelliai_datasets.validate import (
    RejectionReason,
    normalize_text,
    validate_samples,
)


def sample(tmp_path: Path, **overrides: object) -> CandidateSample:
    base: dict[str, object] = {
        "id": "s1",
        "source": "fleurs",
        "language": "hi",
        "split": "test",
        "path": "a.wav",
        "text": "नमस्ते दुनिया",
        "duration_seconds": 5.0,
        "sample_rate_hz": 16000,
        "channels": 1,
        "sha256": "a" * 64,
    }
    base.update(overrides)
    built = CandidateSample.model_validate(base)
    target = tmp_path / built.path
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"x")
    return built


class TestValidation:
    def test_valid_sample_is_accepted(self, tmp_path: Path) -> None:
        accepted, rejections = validate_samples(
            [sample(tmp_path)], expected_language="hi", data_root=tmp_path
        )
        assert len(accepted) == 1
        assert rejections == []

    def test_missing_audio_is_rejected_with_reason(self, tmp_path: Path) -> None:
        missing = sample(tmp_path)
        (tmp_path / missing.path).unlink()
        _, rejections = validate_samples([missing], expected_language="hi", data_root=tmp_path)
        assert rejections[0].reason is RejectionReason.AUDIO_MISSING

    def test_short_and_long_durations_are_rejected(self, tmp_path: Path) -> None:
        short = sample(tmp_path, id="short", path="short.wav", duration_seconds=0.5)
        long = sample(tmp_path, id="long", path="long.wav", duration_seconds=99.0)
        _, rejections = validate_samples([short, long], expected_language="hi", data_root=tmp_path)
        reasons = {r.sample_id: r.reason for r in rejections}
        assert reasons["short"] is RejectionReason.DURATION_TOO_SHORT
        assert reasons["long"] is RejectionReason.DURATION_TOO_LONG

    def test_empty_transcript_is_rejected(self, tmp_path: Path) -> None:
        _, rejections = validate_samples(
            [sample(tmp_path, text="   ")], expected_language="hi", data_root=tmp_path
        )
        assert rejections[0].reason is RejectionReason.EMPTY_TRANSCRIPT

    def test_wrong_language_is_rejected(self, tmp_path: Path) -> None:
        _, rejections = validate_samples(
            [sample(tmp_path, language="ta")], expected_language="hi", data_root=tmp_path
        )
        assert rejections[0].reason is RejectionReason.WRONG_LANGUAGE

    def test_duplicate_audio_is_rejected(self, tmp_path: Path) -> None:
        first = sample(tmp_path, id="one", path="one.wav")
        second = sample(tmp_path, id="two", path="two.wav")  # same sha256
        accepted, rejections = validate_samples(
            [first, second], expected_language="hi", data_root=tmp_path
        )
        assert [s.id for s in accepted] == ["one"]
        assert rejections[0].reason is RejectionReason.DUPLICATE_AUDIO

    def test_eval_contamination_is_rejected(self, tmp_path: Path) -> None:
        _, rejections = validate_samples(
            [sample(tmp_path)],
            expected_language="hi",
            data_root=tmp_path,
            eval_sha256=["A" * 64],  # case-insensitive match
        )
        assert rejections[0].reason is RejectionReason.EVAL_CONTAMINATION

    def test_eval_speaker_overlap_is_rejected(self, tmp_path: Path) -> None:
        _, rejections = validate_samples(
            [sample(tmp_path, speaker_id="SPK-07")],
            expected_language="hi",
            data_root=tmp_path,
            eval_speakers=["SPK-07"],
        )
        assert rejections[0].reason is RejectionReason.SPEAKER_IN_EVAL

    def test_rejections_never_shrink_the_ledger(self, tmp_path: Path) -> None:
        # candidates == accepted + rejected, always.
        good = sample(tmp_path, id="g", path="g.wav", sha256="b" * 64)
        bad = sample(tmp_path, id="b", path="b.wav", text="")
        accepted, rejections = validate_samples(
            [good, bad], expected_language="hi", data_root=tmp_path
        )
        assert len(accepted) + len(rejections) == 2


class TestNormalizeText:
    def test_nfc_and_trim_only(self) -> None:
        composed = "नमस्ते"
        assert normalize_text(f"  {composed}\n") == composed

    def test_case_and_punctuation_survive(self) -> None:
        # Manifest text is near-verbatim; scoring-time normalization is
        # the evaluation plane's versioned job, not ours.
        assert normalize_text("Hello, World!") == "Hello, World!"
