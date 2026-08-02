"""RuntimeMetadata invariants: small, frozen, operational-only."""

import pytest
from pydantic import ValidationError

from intelliai_runtime_contract import CONTRACT_VERSION, RuntimeMetadata


def make() -> RuntimeMetadata:
    return RuntimeMetadata(
        service="stt-runtime",
        service_version="0.1.0",
        contract_version=CONTRACT_VERSION,
    )


class TestInvariants:
    def test_exactly_three_operational_fields(self) -> None:
        # The anti-dumping-ground pin (ADR-0016): adding a field here must
        # break this test, forcing the "is it operational?" review.
        assert set(RuntimeMetadata.model_fields) == {
            "service",
            "service_version",
            "contract_version",
        }

    def test_frozen(self) -> None:
        meta = make()
        with pytest.raises(ValidationError):
            meta.service = "other"  # type: ignore[misc]

    def test_undeclared_fields_are_dropped_not_stored(self) -> None:
        # Tolerant reader: junk is discarded, so metadata cannot become a
        # covert payload channel.
        meta = RuntimeMetadata.model_validate(
            {
                "service": "stt-runtime",
                "service_version": "0.1.0",
                "contract_version": 1,
                "engine": "whisper",  # payload smuggling attempt
            }
        )
        assert "engine" not in meta.model_dump()

    def test_empty_identity_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RuntimeMetadata(service="", service_version="0.1.0", contract_version=1)
        with pytest.raises(ValidationError):
            RuntimeMetadata(service="stt-runtime", service_version="", contract_version=1)

    def test_contract_version_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            RuntimeMetadata(service="stt-runtime", service_version="0.1.0", contract_version=0)


def test_json_round_trip() -> None:
    meta = make()
    assert RuntimeMetadata.model_validate_json(meta.model_dump_json()) == meta
