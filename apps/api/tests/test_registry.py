"""Registry V1: resolution, the license gate, and catalog integrity."""

from datetime import date

import pytest
from pydantic import ValidationError

from intelliai_api.core.errors import ErrorType
from intelliai_api.registry import (
    ArtifactRecord,
    LicenseVerdict,
    ModelNotFoundError,
    PublicModelRecord,
    Registry,
    Resolution,
    default_registry,
)
from intelliai_runtime_contract import Capability

MIT = LicenseVerdict(
    license="MIT",
    commercial_use=True,
    verified_on=date(2026, 7, 31),
    source="https://example.com/license",
)

NON_COMMERCIAL = LicenseVerdict(
    license="CC-BY-NC-4.0",
    commercial_use=False,
    verified_on=date(2026, 7, 31),
    source="https://example.com/license",
)


def artifact(**overrides: object) -> ArtifactRecord:
    fields: dict[str, object] = {
        "id": "whisper-small",
        "version": 1,
        "capability": Capability.TRANSCRIPTION,
        "provenance": "test provenance",
        "license": MIT,
    }
    fields.update(overrides)
    return ArtifactRecord.model_validate(fields)


def model(**overrides: object) -> PublicModelRecord:
    fields: dict[str, object] = {
        "id": "intelliai-stt",
        "capability": Capability.TRANSCRIPTION,
        "service": "stt-runtime",
        "artifact_id": "whisper-small",
    }
    fields.update(overrides)
    return PublicModelRecord.model_validate(fields)


class TestResolution:
    def test_resolves_to_capability_service_and_artifact(self) -> None:
        registry = Registry(artifacts=[artifact()], models=[model()])
        resolution = registry.resolve("intelliai-stt")
        assert resolution == Resolution(
            public_model_id="intelliai-stt",
            capability=Capability.TRANSCRIPTION,
            service="stt-runtime",
            artifact=artifact(),
        )

    def test_unknown_model_raises_not_found_with_public_error_shape(self) -> None:
        registry = Registry(artifacts=[artifact()], models=[model()])
        with pytest.raises(ModelNotFoundError) as exc_info:
            registry.resolve("gpt-4o")
        err = exc_info.value
        assert err.error_type is ErrorType.NOT_FOUND
        assert err.status_code == 404
        assert err.code == "model_not_found"
        assert err.param == "model"
        assert "gpt-4o" in err.message
        assert not err.retryable

    def test_list_models_backs_v1_models_endpoint(self) -> None:
        registry = Registry(artifacts=[artifact()], models=[model()])
        assert [m.id for m in registry.list_models()] == ["intelliai-stt"]


class TestLicenseGate:
    def test_recording_a_non_commercial_artifact_is_legal(self) -> None:
        # Records state facts; the gate is at composition, not at the record.
        assert artifact(license=NON_COMMERCIAL).license.commercial_use is False

    def test_routing_to_a_non_commercial_artifact_cannot_compose(self) -> None:
        with pytest.raises(ValueError, match="commercial-use"):
            Registry(artifacts=[artifact(license=NON_COMMERCIAL)], models=[model()])

    def test_unrouted_non_commercial_artifact_may_exist(self) -> None:
        # An artifact under evaluation can sit in the catalog unrouted.
        registry = Registry(
            artifacts=[artifact(), artifact(id="research-only", license=NON_COMMERCIAL)],
            models=[model()],
        )
        assert registry.resolve("intelliai-stt").artifact.id == "whisper-small"


class TestCatalogIntegrity:
    def test_route_to_unknown_artifact_cannot_compose(self) -> None:
        with pytest.raises(ValueError, match="unknown artifact"):
            Registry(artifacts=[artifact()], models=[model(artifact_id="missing")])

    # NOTE: the Registry also rejects a public model whose capability differs
    # from its artifact's. With a single Capability member the mismatch is
    # unconstructible, so that branch becomes testable when M3 adds the second
    # member — add the test in the same change.

    def test_duplicate_ids_cannot_compose(self) -> None:
        with pytest.raises(ValueError, match="duplicate artifact"):
            Registry(artifacts=[artifact(), artifact()], models=[model()])
        with pytest.raises(ValueError, match="duplicate public model"):
            Registry(artifacts=[artifact()], models=[model(), model()])

    def test_records_are_frozen_and_reject_unknown_fields(self) -> None:
        record = artifact()
        with pytest.raises(ValidationError):
            record.id = "other"  # type: ignore[misc]
        with pytest.raises(ValidationError):
            artifact(precision="int8")  # build concern — never identity (ADR-0015)


class TestDefaultCatalog:
    def test_composes_and_serves_intelliai_stt(self) -> None:
        resolution = default_registry().resolve("intelliai-stt")
        assert resolution.capability is Capability.TRANSCRIPTION
        assert resolution.service == "stt-runtime"
        assert resolution.artifact.id == "whisper-small"

    def test_every_routed_artifact_passed_the_license_gate(self) -> None:
        registry = default_registry()
        for public_model in registry.list_models():
            verdict = registry.resolve(public_model.id).artifact.license
            assert verdict.commercial_use is True
            assert verdict.verified_on <= date(2026, 12, 31)
            assert verdict.source.startswith("https://")

    def test_public_ids_never_leak_engine_names(self) -> None:
        # The product boundary: customers see intelliai-*, never engines.
        for public_model in default_registry().list_models():
            assert public_model.id.startswith("intelliai-")
