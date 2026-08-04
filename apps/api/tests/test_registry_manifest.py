"""The resolution manifest: registry state, exported and kept honest.

The manifest is a projection, never a second source of truth — so the
committed copy must never disagree with the registry that produced it.
The drift guard below is the whole reason a file can be trusted by a
package that cannot import the registry.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from intelliai_api.registry import (
    ArtifactRecord,
    LanguageStatus,
    LicenseVerdict,
    PublicModelRecord,
    PublicVoiceRecord,
    Registry,
    RouteSelector,
    ServingRoute,
    default_registry,
)
from intelliai_api.registry.manifest import MANIFEST_SCHEMA_VERSION, serving_manifest
from intelliai_runtime_contract import Capability

COMMITTED = Path("ml/evaluation/manifests/resolution.json")

MIT = LicenseVerdict(
    license="MIT",
    commercial_use=True,
    verified_on=date(2026, 7, 31),
    source="https://example.com/license",
    covers="the whole serving path for this route",
)


def test_the_committed_manifest_matches_the_registry_that_produced_it() -> None:
    # The drift guard. Without it, the evaluation plane could be measuring
    # against a routing table the platform stopped using months ago —
    # silently, and with every record looking correct.
    committed = json.loads(COMMITTED.read_text(encoding="utf-8"))
    assert committed == serving_manifest(default_registry()), (
        "the committed resolution manifest is stale; regenerate it with "
        "`python -m intelliai_api.cli registry-manifest --out ml/evaluation/manifests/"
        "resolution.json`"
    )


def test_export_is_deterministic() -> None:
    # Same catalog, same bytes: a manifest that reordered itself would
    # make the drift guard flap and train everyone to ignore it.
    assert serving_manifest(default_registry()) == serving_manifest(default_registry())


def test_the_schema_version_is_declared() -> None:
    assert serving_manifest(default_registry())["schema_version"] == MANIFEST_SCHEMA_VERSION


class TestProjection:
    def _registry(self) -> Registry:
        artifacts = [
            ArtifactRecord(
                id=artifact_id,
                version=version,
                capability=Capability.TRANSCRIPTION,
                provenance="manifest test",
                license=MIT,
            )
            for artifact_id, version in (("whisper-small", 1), ("future-hi-v1", 7))
        ]
        return Registry(
            artifacts=artifacts,
            models=[
                PublicModelRecord(
                    id="intelliai-stt",
                    capability=Capability.TRANSCRIPTION,
                    service="stt-runtime",
                    artifact_id="whisper-small",
                    released=date(2026, 8, 2),
                )
            ],
            routes=[
                ServingRoute(
                    public_model_id="intelliai-stt",
                    selector=RouteSelector(language="hi"),
                    status=LanguageStatus.AVAILABLE,
                    artifact_id="future-hi-v1",
                    deployment="stt-runtime-indic",
                    license=MIT,
                ),
                ServingRoute(
                    public_model_id="intelliai-stt",
                    selector=RouteSelector(language="ar"),
                    status=LanguageStatus.UNAVAILABLE,
                ),
            ],
        )

    def _routes(self) -> dict[str | None, dict[str, object]]:
        (model,) = serving_manifest(self._registry())["models"]
        return {route["language"]: route for route in model["routes"]}

    def test_every_entry_is_pre_resolved(self) -> None:
        # The reader looks up an exact key; it never re-implements the
        # Specificity Law, because a reader that falls back is a router.
        routes = self._routes()
        assert routes["hi"]["artifact"] == "future-hi-v1"
        assert routes["hi"]["artifact_version"] == 7
        assert routes["hi"]["deployment"] == "stt-runtime-indic"

    def test_the_default_route_is_its_own_entry_not_a_wildcard(self) -> None:
        default = self._routes()[None]
        assert default["artifact"] == "whisper-small"
        assert default["status"] is None  # the default route carries no rung

    def test_a_refused_language_exports_a_refusal_not_an_artifact(self) -> None:
        refused = self._routes()["ar"]
        assert refused["status"] == "unavailable"
        assert "artifact" not in refused

    def test_voices_export_the_artifact_that_renders_them(self) -> None:
        registry = Registry(
            artifacts=[
                ArtifactRecord(
                    id="kokoro-82m",
                    version=1,
                    capability=Capability.SPEECH_SYNTHESIS,
                    provenance="manifest test",
                    license=MIT,
                )
            ],
            models=[
                PublicModelRecord(
                    id="intelliai-tts",
                    capability=Capability.SPEECH_SYNTHESIS,
                    service="tts-runtime",
                    artifact_id="kokoro-82m",
                    released=date(2026, 8, 3),
                )
            ],
            voices=[
                PublicVoiceRecord(
                    id="reference-alto",
                    model="intelliai-tts",
                    languages=("en",),
                    released=date(2026, 8, 3),
                )
            ],
        )
        (model,) = serving_manifest(registry)["models"]
        (voice,) = model["voices"]
        assert voice == {
            "voice": "reference-alto",
            "languages": ["en"],
            "artifact": "kokoro-82m",
            "artifact_version": 1,
            "deployment": "tts-runtime",
        }


def test_the_manifest_carries_no_engine_vocabulary() -> None:
    # It crosses a package boundary into a repo area with no leak-guard
    # of its own; keeping engine names out of it means a careless reader
    # cannot publish one.
    text = json.dumps(serving_manifest(default_registry())).lower()
    for term in ("faster-whisper", "ctranslate2", "espeak", "hexgrad", "af_heart"):
        assert term not in text


@pytest.mark.parametrize("model_id", ["intelliai-stt", "intelliai-tts"])
def test_every_public_model_is_exported(model_id: str) -> None:
    exported = {model["public_model"] for model in serving_manifest(default_registry())["models"]}
    assert model_id in exported
