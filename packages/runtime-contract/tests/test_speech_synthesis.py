"""Speech synthesis capability schemas."""

import pytest
from pydantic import ValidationError

from intelliai_runtime_contract import (
    RuntimeMetadata,
    RuntimeResponse,
    RuntimeTiming,
    SpeechSynthesisRequest,
    SpeechSynthesisResponse,
    SpeechSynthesisResult,
    Usage,
    UsageUnit,
)


class TestRequest:
    def test_defaults_to_default_voice_on_the_default_slot(self) -> None:
        request = SpeechSynthesisRequest(text="hello")
        assert request.voice is None  # None = the runtime's default voice
        assert request.language is None
        assert request.speed is None  # None = the voice's natural pace
        assert request.model is None  # None = the runtime's default slot

    def test_empty_text_is_rejected(self) -> None:
        # The inverse of transcription's empty-result rule: an empty
        # TRANSCRIPT is valid evidence, but empty INPUT is a caller error —
        # there is nothing to synthesize.
        with pytest.raises(ValidationError):
            SpeechSynthesisRequest(text="")

    def test_speed_must_be_positive_when_present(self) -> None:
        with pytest.raises(ValidationError):
            SpeechSynthesisRequest(text="hi", speed=0)
        with pytest.raises(ValidationError):
            SpeechSynthesisRequest(text="hi", speed=-1.0)
        assert SpeechSynthesisRequest(text="hi", speed=1.25).speed == 1.25

    def test_tolerates_unknown_params_from_newer_gateway(self) -> None:
        req = SpeechSynthesisRequest.model_validate(
            {"text": "hello", "voice": "intelliai-aurora", "emotion": "calm"}
        )
        assert req.voice == "intelliai-aurora"
        assert "emotion" not in req.model_dump()


class TestResult:
    def test_carries_facts_about_audio_never_audio(self) -> None:
        # The audio travels as the transport body (ADR-0020); the contract
        # models only its metadata. No bytes field may ever exist here.
        result = SpeechSynthesisResult(
            duration_seconds=2.4, sample_rate_hz=24_000, voice="intelliai-aurora", characters=42
        )
        assert "audio" not in result.model_dump()
        assert result.characters == 42

    def test_served_voice_is_required_nonempty(self) -> None:
        # Default resolution must be made visible: the runtime always says
        # WHICH voice served, even when the caller didn't choose one.
        with pytest.raises(ValidationError):
            SpeechSynthesisResult(
                duration_seconds=1.0, sample_rate_hz=24_000, voice="", characters=1
            )

    def test_zero_duration_and_zero_characters_are_valid_measurements(self) -> None:
        result = SpeechSynthesisResult(
            duration_seconds=0, sample_rate_hz=24_000, voice="intelliai-aurora", characters=0
        )
        assert result.duration_seconds == 0

    def test_round_trip(self) -> None:
        result = SpeechSynthesisResult(
            duration_seconds=2.4, sample_rate_hz=24_000, voice="intelliai-aurora", characters=42
        )
        assert SpeechSynthesisResult.model_validate_json(result.model_dump_json()) == result


class TestEnvelope:
    def test_synthesis_response_alias_is_the_generic_envelope(self) -> None:
        # The exported convenience alias must stay exactly the generic shape.
        assert SpeechSynthesisResponse is RuntimeResponse[SpeechSynthesisResult]

    def test_bills_in_characters_through_the_standard_envelope(self) -> None:
        response = SpeechSynthesisResponse(
            output=SpeechSynthesisResult(
                duration_seconds=2.4,
                sample_rate_hz=24_000,
                voice="intelliai-aurora",
                characters=42,
            ),
            model="kokoro-82m",
            usage=(Usage(unit=UsageUnit.CHARACTERS, amount=42),),
            timing=RuntimeTiming(total_ms=180.0),
            runtime=RuntimeMetadata(
                service="tts-runtime", service_version="0.1.0", contract_version=1
            ),
        )
        wire = response.model_dump_json()
        parsed = SpeechSynthesisResponse.model_validate_json(wire)
        assert parsed == response
        assert parsed.usage[0].unit is UsageUnit.CHARACTERS
