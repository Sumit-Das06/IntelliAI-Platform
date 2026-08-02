"""Envelope shape, usage/timing vocabulary, and cross-version tolerance."""

import pytest
from pydantic import ValidationError

from intelliai_runtime_contract import (
    RuntimeMetadata,
    RuntimeResponse,
    RuntimeTiming,
    TranscriptionResult,
    Usage,
    UsageUnit,
)

META = RuntimeMetadata(service="stt-runtime", service_version="0.1.0", contract_version=1)


class TestUsage:
    def test_unit_vocabulary_is_exactly_this(self) -> None:
        assert {member.name: member.value for member in UsageUnit} == {
            "AUDIO_SECONDS": "audio_seconds",
        }

    def test_amount_never_negative(self) -> None:
        with pytest.raises(ValidationError):
            Usage(unit=UsageUnit.AUDIO_SECONDS, amount=-0.1)

    def test_zero_is_a_valid_measurement(self) -> None:
        assert Usage(unit=UsageUnit.AUDIO_SECONDS, amount=0).amount == 0


class TestTiming:
    def test_stages_default_empty_and_total_required(self) -> None:
        timing = RuntimeTiming(total_ms=12.5)
        assert timing.stages == {}

    def test_negative_total_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RuntimeTiming(total_ms=-1)


def make_response() -> RuntimeResponse[TranscriptionResult]:
    return RuntimeResponse[TranscriptionResult](
        output=TranscriptionResult(text="hello", language="en", duration_seconds=1.2),
        model="whisper-small-int8",
        usage=(Usage(unit=UsageUnit.AUDIO_SECONDS, amount=1.2),),
        timing=RuntimeTiming(total_ms=340.0, stages={"decode": 40.0, "inference": 300.0}),
        runtime=META,
    )


class TestResponseEnvelope:
    def test_json_round_trip(self) -> None:
        resp = make_response()
        wire = resp.model_dump_json()
        parsed = RuntimeResponse[TranscriptionResult].model_validate_json(wire)
        assert parsed == resp
        assert parsed.output.text == "hello"
        assert parsed.usage[0].unit is UsageUnit.AUDIO_SECONDS

    def test_frozen_and_usage_is_immutable_tuple(self) -> None:
        resp = make_response()
        assert isinstance(resp.usage, tuple)
        with pytest.raises(ValidationError):
            resp.model = "other"  # type: ignore[misc]

    def test_model_identifier_required_nonempty(self) -> None:
        with pytest.raises(ValidationError):
            RuntimeResponse[TranscriptionResult](
                output=TranscriptionResult(text="", language="en", duration_seconds=0),
                model="",
                timing=RuntimeTiming(total_ms=1),
                runtime=META,
            )

    def test_tolerates_fields_from_a_newer_contract(self) -> None:
        # Backwards-compatibility expectation (ADR-0016): a newer sender may
        # add fields at ANY level; this reader drops them instead of failing.
        payload = make_response().model_dump()
        payload["confidence"] = 0.97  # future envelope field
        payload["output"]["words"] = []  # future output field
        payload["runtime"]["region"] = "local"  # future metadata field
        parsed = RuntimeResponse[TranscriptionResult].model_validate(payload)
        assert parsed.output.text == "hello"
        assert "confidence" not in parsed.model_dump()
