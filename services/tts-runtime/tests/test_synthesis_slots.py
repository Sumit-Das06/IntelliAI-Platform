"""The deployment slot catalog: declaration in, validated slots out.

A misdeclared deployment must fail at startup, never at request time —
the same fail-fast posture as Settings and the registry catalog.
"""

import pytest
from pydantic import ValidationError

from intelliai_tts_runtime.config import Settings
from intelliai_tts_runtime.slots import CATALOG, build_slot_specs
from intelliai_tts_runtime.voices import VoiceCatalog


def specs(declaration: str) -> list[tuple[str, str]]:
    return [
        (spec.slot, spec.artifact)
        for spec in build_slot_specs(Settings(slots=declaration), VoiceCatalog())
    ]


class TestDeclaration:
    def test_the_default_deployment_is_one_reference_slot(self) -> None:
        assert specs("reference") == [("default", "reference")]

    def test_a_deployment_may_host_several_artifacts(self) -> None:
        assert specs("reference,reference:future-hi-v1,reference:future-ar-v1") == [
            ("default", "reference"),
            ("future-hi-v1", "future-hi-v1"),
            ("future-ar-v1", "future-ar-v1"),
        ]

    def test_the_first_declaration_takes_the_default_slot(self) -> None:
        # `default` is a ROLE — which hosted artifact answers a request
        # that pins nothing — never an identity.
        assert specs("reference:future-hi-v1,reference")[0] == ("default", "future-hi-v1")

    def test_whitespace_and_empty_entries_are_tolerated(self) -> None:
        assert specs(" reference , reference:future-hi-v1 ,") == [
            ("default", "reference"),
            ("future-hi-v1", "future-hi-v1"),
        ]

    def test_a_real_engine_declares_its_pinned_files(self) -> None:
        # No loading happens here: declaring is not hosting.
        (spec,) = build_slot_specs(Settings(slots="kokoro"), VoiceCatalog())
        assert (spec.slot, spec.artifact) == ("default", "kokoro-82m")
        assert spec.files is not None
        assert spec.files.artifact == "kokoro-82m"


class TestDeclarationRefusals:
    def test_an_unknown_engine_names_what_can_be_hosted(self) -> None:
        with pytest.raises(ValueError, match="unknown engine"):
            specs("elevenlabs")

    def test_an_engine_with_weights_cannot_be_relabelled(self) -> None:
        # Identity is the weights: a kokoro process may not claim to host
        # some other artifact.
        with pytest.raises(ValueError, match="carries weights"):
            specs("kokoro:future-hi-v1")

    def test_one_artifact_is_hosted_once(self) -> None:
        with pytest.raises(ValueError, match="declared twice"):
            specs("reference,reference")

    def test_an_empty_declaration_hosts_nothing_and_says_so(self) -> None:
        with pytest.raises(ValueError, match="names nothing to host"):
            specs("  , ")

    def test_the_default_slot_role_is_not_an_artifact_identity(self) -> None:
        with pytest.raises(ValueError, match="slot role"):
            specs("reference:default")


class TestReplacedSetting:
    def test_the_old_single_engine_setting_fails_loudly(self) -> None:
        # A stale INTELLIAI_TTS_DEFAULT_ENGINE would otherwise be ignored
        # and a kokoro deployment would come up serving the reference
        # engine — healthy, and wrong.
        with pytest.raises(ValidationError, match="INTELLIAI_TTS_SLOTS"):
            Settings(default_engine="kokoro")


class TestCatalog:
    def test_only_weightless_engines_may_be_relabelled(self) -> None:
        for name, binding in CATALOG.items():
            assert binding.weightless == (binding.files is None), name

    def test_every_hostable_engine_declares_its_voices(self) -> None:
        # A slot without voices could load and then fail its own warm-up:
        # the binding must be complete before the deployment can declare it.
        for name, binding in CATALOG.items():
            assert binding.voices.voice_ids(), name
