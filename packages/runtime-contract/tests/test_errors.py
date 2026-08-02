"""Runtime failure taxonomy: frozen vocabulary, transport-free payload."""

import pytest
from pydantic import ValidationError

from intelliai_runtime_contract import (
    RuntimeErrorResponse,
    RuntimeErrorType,
    RuntimeMetadata,
)

META = RuntimeMetadata(service="stt-runtime", service_version="0.1.0", contract_version=1)


class TestErrorTypeGolden:
    def test_complete_taxonomy_is_exactly_this(self) -> None:
        assert {member.name: member.value for member in RuntimeErrorType} == {
            "INVALID_INPUT": "invalid_input",
            "NOT_READY": "not_ready",
            "OVERLOADED": "overloaded",
            "INTERNAL": "internal",
        }

    def test_unknown_type_rejected(self) -> None:
        with pytest.raises(ValueError, match="timeout"):
            RuntimeErrorType("timeout")


class TestErrorResponse:
    def test_round_trip(self) -> None:
        err = RuntimeErrorResponse(
            type=RuntimeErrorType.OVERLOADED,
            message="all worker slots busy",
            runtime=META,
        )
        parsed = RuntimeErrorResponse.model_validate_json(err.model_dump_json())
        assert parsed == err
        assert parsed.param is None

    def test_wire_type_is_the_enum_value(self) -> None:
        err = RuntimeErrorResponse(
            type=RuntimeErrorType.INVALID_INPUT,
            message="unsupported container",
            param="file",
            runtime=META,
        )
        assert '"invalid_input"' in err.model_dump_json()

    def test_message_is_required_and_nonempty(self) -> None:
        with pytest.raises(ValidationError):
            RuntimeErrorResponse(type=RuntimeErrorType.INTERNAL, message="", runtime=META)

    def test_carries_no_transport_fields(self) -> None:
        # The contract never knows HTTP: no status codes, no retry hints.
        assert {"status", "status_code", "retryable", "retry_after"}.isdisjoint(
            RuntimeErrorResponse.model_fields
        )
