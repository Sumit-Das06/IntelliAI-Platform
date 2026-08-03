"""Capability vocabulary stability.

The golden test pins the COMPLETE member->value mapping. Any addition,
rename, removal, or value change fails it — which is the point: vocabulary
changes must be conscious, reviewed, append-only decisions (ADR-0016).
"""

import json

import pytest

from intelliai_runtime_contract import Capability


class TestCapabilityGolden:
    def test_complete_vocabulary_is_exactly_this(self) -> None:
        assert {member.name: member.value for member in Capability} == {
            "TRANSCRIPTION": "transcription",
            "SPEECH_SYNTHESIS": "speech_synthesis",
        }

    def test_values_are_lowercase_snake_case(self) -> None:
        for member in Capability:
            assert member.value == member.value.lower()
            assert " " not in member.value


class TestCapabilityParsing:
    def test_parses_from_wire_string(self) -> None:
        assert Capability("transcription") is Capability.TRANSCRIPTION

    def test_unknown_identifier_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="asr"):
            Capability("asr")

    def test_is_a_string_on_the_wire(self) -> None:
        assert isinstance(Capability.TRANSCRIPTION, str)
        assert json.dumps(Capability.TRANSCRIPTION) == '"transcription"'
        assert str(Capability.TRANSCRIPTION) == "transcription"
