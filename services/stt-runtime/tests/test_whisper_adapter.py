"""FasterWhisperEngine's contract adaptation — pure logic, no library.

The conversion is tested with duck-typed stand-ins for faster-whisper's
segment objects, so this suite runs everywhere (CI has no model
libraries). The real model runs in the local tier (test_whisper_local).
"""

from dataclasses import dataclass

from helpers import make_audio
from intelliai_stt_runtime.engines.whisper import ARTIFACT_ID, WHISPER_SMALL_FILES, convert_segments


@dataclass
class StubSegment:
    start: float
    end: float
    text: str


class TestConvertSegments:
    def test_segments_become_contract_shape(self) -> None:
        audio = make_audio(duration_seconds=2.0)
        result = convert_segments(
            [StubSegment(0.0, 1.1, " Ask not"), StubSegment(1.1, 2.0, " what your country")],
            "en",
            audio,
        )
        assert result.text == "Ask not what your country"
        assert result.language == "en"
        assert result.duration_seconds == 2.0
        assert [segment.text for segment in result.segments] == ["Ask not", "what your country"]
        assert result.segments[0].start_seconds == 0.0
        assert result.segments[1].end_seconds == 2.0

    def test_empty_segments_yield_empty_transcript(self) -> None:
        result = convert_segments([], "en", make_audio(duration_seconds=1.0))
        assert result.text == ""
        assert result.segments == ()

    def test_whitespace_only_segments_are_dropped(self) -> None:
        result = convert_segments(
            [StubSegment(0.0, 0.5, "   "), StubSegment(0.5, 1.0, " real ")],
            None,
            make_audio(duration_seconds=1.0),
        )
        assert result.text == "real"
        assert len(result.segments) == 1
        assert result.language == "und"  # detection unavailable -> undetermined

    def test_negative_timestamps_are_clamped(self) -> None:
        result = convert_segments(
            [StubSegment(-0.2, 0.5, "clamped")], "en", make_audio(duration_seconds=1.0)
        )
        assert result.segments[0].start_seconds == 0.0


class TestArtifactSpec:
    def test_identity_matches_the_registry_artifact(self) -> None:
        assert ARTIFACT_ID == "whisper-small"
        assert WHISPER_SMALL_FILES.artifact == ARTIFACT_ID
        assert WHISPER_SMALL_FILES.version == 1

    def test_every_file_is_hash_pinned(self) -> None:
        filenames = {file.filename for file in WHISPER_SMALL_FILES.files}
        assert filenames == {"model.bin", "config.json", "tokenizer.json", "vocabulary.txt"}
        for file in WHISPER_SMALL_FILES.files:
            assert len(file.sha256) == 64
            assert file.url.startswith("https://")

    def test_identity_carries_no_precision(self) -> None:
        # ADR-0015: int8 is a build/deployment concern, never identity.
        assert "int8" not in ARTIFACT_ID
        assert "float" not in ARTIFACT_ID
