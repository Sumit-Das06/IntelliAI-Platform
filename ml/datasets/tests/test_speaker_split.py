"""Speaker-disjointness machinery: curation, roster, enforcement, no leaks."""

from pathlib import Path

import pytest

from intelliai_datasets.curate import curate_speakers, speaker_roster
from intelliai_datasets.samples import CandidateSample
from intelliai_datasets.validate import RejectionReason, validate_samples


def sample(sample_id: str, sha: str, speaker: str | None, duration: float = 5.0) -> CandidateSample:
    return CandidateSample(
        id=sample_id,
        source="indicvoices",
        language="hi",
        split="valid",
        path=f"{sample_id}.wav",
        text="नमस्ते दुनिया",
        duration_seconds=duration,
        sample_rate_hz=16000,
        channels=1,
        sha256=sha.ljust(64, "0"),
        speaker_id=speaker,
    )


class TestSpeakerCuration:
    def test_selection_is_input_order_independent(self) -> None:
        pool = [sample(f"c{i}", f"{i:02x}", f"SPK-{i % 4}") for i in range(12)]
        forward = curate_speakers(pool, target_clips=6, max_per_speaker=3)
        backward = curate_speakers(list(reversed(pool)), target_clips=6, max_per_speaker=3)
        assert forward == backward

    def test_speakers_are_taken_whole_up_to_the_cap(self) -> None:
        pool = [sample(f"c{i}", f"{i:02x}", "SPK-A") for i in range(10)] + [
            sample(f"d{i}", f"a{i:01x}", "SPK-B") for i in range(2)
        ]
        chosen = curate_speakers(pool, target_clips=5, max_per_speaker=4)
        per_speaker: dict[str, int] = {}
        for s in chosen:
            assert s.speaker_id is not None
            per_speaker[s.speaker_id] = per_speaker.get(s.speaker_id, 0) + 1
        assert all(count <= 4 for count in per_speaker.values())

    def test_missing_speaker_id_is_refused_loudly(self) -> None:
        with pytest.raises(ValueError, match="without speaker_id"):
            curate_speakers([sample("x", "aa", None)], target_clips=1, max_per_speaker=1)

    def test_roster_is_sorted_and_deduplicated(self) -> None:
        chosen = [sample("a", "aa", "Z"), sample("b", "bb", "A"), sample("c", "cc", "Z")]
        assert speaker_roster(chosen) == ("A", "Z")


class TestRosterEnforcement:
    def test_roster_speaker_is_rejected_from_training(self, tmp_path: Path) -> None:
        candidate = sample("t1", "dd", "SPK-EVAL-7")
        (tmp_path / candidate.path).write_bytes(b"x")
        _, rejections = validate_samples(
            [candidate],
            expected_language="hi",
            data_root=tmp_path,
            eval_speakers=["SPK-EVAL-7"],
        )
        assert rejections[0].reason is RejectionReason.SPEAKER_IN_EVAL

    def test_require_speaker_ids_rejects_unattributable_samples(self, tmp_path: Path) -> None:
        candidate = sample("t2", "ee", None)
        (tmp_path / candidate.path).write_bytes(b"x")
        accepted, rejections = validate_samples(
            [candidate],
            expected_language="hi",
            data_root=tmp_path,
            require_speaker_ids=True,
        )
        assert accepted == []
        assert rejections[0].reason is RejectionReason.MISSING_SPEAKER_ID


class TestTokenHygiene:
    def test_discover_token_reads_env_without_printing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from intelliai_datasets.hf import discover_token

        monkeypatch.setenv("HF_TOKEN", "hf_test_value_never_logged")
        assert discover_token() == "hf_test_value_never_logged"

    def test_file_fallback_is_used_when_env_is_absent(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from intelliai_datasets import hf

        monkeypatch.delenv("HF_TOKEN", raising=False)
        monkeypatch.delenv("HUGGING_FACE_HUB_TOKEN", raising=False)
        token_file = tmp_path / "token"
        token_file.write_text("hf_from_file\n", encoding="utf-8")
        monkeypatch.setattr(hf, "_TOKEN_FILE", token_file)
        assert hf.discover_token() == "hf_from_file"

    def test_the_token_travels_only_in_headers(self) -> None:
        # The client carries the secret as an Authorization header; it is
        # never interpolated into URLs or error text.
        from intelliai_datasets import hf

        with hf.client("hf_secret_probe") as http:
            assert http.headers["Authorization"] == "Bearer hf_secret_probe"
        error = hf.HfAccessError("dataset x: access refused (missing/insufficient token)")
        assert "hf_secret_probe" not in str(error)
