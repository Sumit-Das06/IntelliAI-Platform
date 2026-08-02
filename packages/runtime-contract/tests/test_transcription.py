"""Transcription capability schemas."""

import pytest
from pydantic import ValidationError

from intelliai_runtime_contract import (
    RuntimeResponse,
    TranscriptionRequest,
    TranscriptionResponse,
    TranscriptionResult,
    TranscriptionSegment,
)


class TestRequest:
    def test_defaults_to_auto_detect(self) -> None:
        assert TranscriptionRequest().language is None

    def test_tolerates_unknown_params_from_newer_gateway(self) -> None:
        req = TranscriptionRequest.model_validate({"language": "hi", "temperature": 0.2})
        assert req.language == "hi"
        assert "temperature" not in req.model_dump()


class TestSegment:
    def test_end_before_start_rejected(self) -> None:
        with pytest.raises(ValidationError, match="start_seconds"):
            TranscriptionSegment(start_seconds=2.0, end_seconds=1.0, text="x")

    def test_zero_length_segment_allowed(self) -> None:
        seg = TranscriptionSegment(start_seconds=1.0, end_seconds=1.0, text="")
        assert seg.end_seconds == seg.start_seconds


class TestResult:
    def test_empty_text_is_a_valid_result(self) -> None:
        # For silence, the CORRECT transcription is nothing — the contract
        # must let a runtime say so (hallucination probes depend on it).
        result = TranscriptionResult(text="", language="zxx", duration_seconds=10.0)
        assert result.text == ""
        assert result.segments == ()

    def test_language_required(self) -> None:
        with pytest.raises(ValidationError):
            TranscriptionResult(text="hi", language="", duration_seconds=1.0)

    def test_round_trip_with_segments(self) -> None:
        result = TranscriptionResult(
            text="ask not",
            language="en",
            duration_seconds=11.0,
            segments=(TranscriptionSegment(start_seconds=0.0, end_seconds=2.1, text="ask not"),),
        )
        assert TranscriptionResult.model_validate_json(result.model_dump_json()) == result


def test_transcription_response_alias_is_the_generic_envelope() -> None:
    # The exported convenience alias must stay exactly the generic shape.
    assert TranscriptionResponse is RuntimeResponse[TranscriptionResult]
