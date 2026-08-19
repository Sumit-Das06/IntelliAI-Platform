"""Reading registry state — and the routing this reader refuses to do."""

import json
from pathlib import Path

import pytest

from intelliai_evaluation.resolution import (
    ResolutionManifest,
    UnservedError,
    load_manifest,
)

COMMITTED = Path("ml/evaluation/manifests/resolution.json")

DOCUMENT = {
    "schema_version": 1,
    "models": [
        {
            "public_model": "intelliai-stt",
            "capability": "transcription",
            "service": "stt-runtime",
            "routes": [
                {
                    "language": None,
                    "status": None,
                    "artifact": "whisper-small",
                    "artifact_version": 1,
                    "deployment": "stt-runtime",
                },
                {
                    "language": "hi",
                    "status": "available",
                    "artifact": "future-hi-v1",
                    "artifact_version": 3,
                    "deployment": "stt-runtime-indic",
                },
                {"language": "ar", "status": "unavailable"},
            ],
            "voices": [],
        }
    ],
}


def manifest() -> ResolutionManifest:
    return ResolutionManifest.model_validate(DOCUMENT)


class TestResolution:
    def test_a_language_route_resolves_to_its_own_artifact_and_deployment(self) -> None:
        served = manifest().resolve("intelliai-stt", "hi")
        assert (served.artifact, served.artifact_version) == ("future-hi-v1", 3)
        assert served.deployment == "stt-runtime-indic"
        assert served.status == "available"

    def test_the_default_route_has_its_own_key_and_no_ladder_rung(self) -> None:
        served = manifest().resolve("intelliai-stt", None)
        assert served.artifact == "whisper-small"
        assert served.status is None


class TestRefusals:
    """The reader never routes — every miss is a refusal, never a fallback."""

    def test_an_unrouted_language_does_not_fall_back_to_the_default(self) -> None:
        with pytest.raises(UnservedError, match="that would be routing"):
            manifest().resolve("intelliai-stt", "fr")

    def test_a_refused_language_has_nothing_to_evaluate(self) -> None:
        with pytest.raises(UnservedError, match="nothing to evaluate"):
            manifest().resolve("intelliai-stt", "ar")

    def test_an_unknown_model_names_what_the_manifest_holds(self) -> None:
        with pytest.raises(UnservedError, match="intelliai-stt"):
            manifest().resolve("intelliai-ocr", "en")

    def test_an_unknown_schema_is_refused_rather_than_guessed_at(self, tmp_path: Path) -> None:
        path = tmp_path / "resolution.json"
        path.write_text(json.dumps({**DOCUMENT, "schema_version": 99}), encoding="utf-8")
        with pytest.raises(UnservedError, match="refusing rather than guessing"):
            load_manifest(path)


class TestCommittedManifest:
    """The real registry state the evaluation plane reads."""

    def test_it_loads_and_resolves_the_policy_languages(self) -> None:
        # M26: Hindi serves the promoted specialist; English and Arabic
        # stay on the incumbent.
        registry = load_manifest(COMMITTED)
        assert registry.resolve("intelliai-stt", "hi").artifact == "qwen3-asr-0.6b-hi-ft-e3"
        for language in ("en", "ar"):
            served = registry.resolve("intelliai-stt", language)
            assert served.artifact == "whisper-small"
            assert served.deployment == "stt-runtime"

    def test_synthesis_refuses_the_languages_the_ladder_refuses(self) -> None:
        registry = load_manifest(COMMITTED)
        assert registry.resolve("intelliai-tts", "en").artifact == "kokoro-82m"
        for language in ("hi", "ar"):
            with pytest.raises(UnservedError, match="nothing to evaluate"):
                registry.resolve("intelliai-tts", language)

    def test_voices_resolve_to_the_artifact_that_renders_them(self) -> None:
        registry = load_manifest(COMMITTED)
        voice = registry.resolve_voice("intelliai-tts", "reference-alto")
        assert voice.artifact == "kokoro-82m"
        assert voice.languages == ["en"]

    def test_it_carries_no_engine_names(self) -> None:
        # The manifest crosses a package boundary; it must not carry
        # vocabulary that the leak-guard forbids on public surfaces, so
        # that a reader cannot accidentally publish one.
        text = COMMITTED.read_text(encoding="utf-8").lower()
        for term in ("faster-whisper", "kokoro-82m-engine", "espeak", "ctranslate2"):
            assert term not in text
