"""The deployment slot catalog: declaration in, validated slots out.

A misdeclared deployment must fail at startup, never at request time —
the same fail-fast posture as Settings and the registry catalog.
"""

import pytest
from pydantic import ValidationError

from intelliai_stt_runtime.config import Settings
from intelliai_stt_runtime.slots import CATALOG, build_slot_specs


def specs(declaration: str) -> list[tuple[str, str]]:
    return [(spec.slot, spec.artifact) for spec in build_slot_specs(Settings(slots=declaration))]


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
        (spec,) = build_slot_specs(Settings(slots="whisper"))
        assert (spec.slot, spec.artifact) == ("default", "whisper-small")
        assert spec.files is not None
        assert spec.files.artifact == "whisper-small"


class TestDeclarationRefusals:
    def test_an_unknown_engine_names_what_can_be_hosted(self) -> None:
        with pytest.raises(ValueError, match="unknown engine"):
            specs("deepgram")

    def test_an_engine_with_weights_cannot_be_relabelled(self) -> None:
        # Identity is the weights: a whisper process may not claim to
        # host some other artifact.
        with pytest.raises(ValueError, match="carries weights"):
            specs("whisper:future-hi-v1")

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
        # A stale INTELLIAI_STT_DEFAULT_ENGINE would otherwise be ignored
        # and a whisper deployment would come up serving the reference
        # engine — healthy, and wrong.
        with pytest.raises(ValidationError, match="INTELLIAI_STT_SLOTS"):
            Settings(default_engine="whisper")


class TestCatalog:
    def test_only_weightless_engines_may_be_relabelled(self) -> None:
        for name, binding in CATALOG.items():
            assert binding.weightless == (binding.files is None), name


class TestChallengerAdmission:
    """A weightful override SELECTS a registered pinned artifact (B6).

    Identity still comes from the pinned bytes; the declaration only
    chooses which pinned identity a deployment hosts. Admission of a new
    checkpoint of an operated family is one data entry in the engine's
    artifact table — never a code change, never a free declaration.
    """

    def test_a_registered_challenger_is_hostable_by_declaration(self) -> None:
        assert specs("whisper:whisper-base") == [("default", "whisper-base")]

    def test_the_challenger_carries_its_own_pinned_files(self) -> None:
        (spec,) = build_slot_specs(Settings(slots="whisper:whisper-base"))
        assert spec.files is not None
        assert spec.files.artifact == "whisper-base"
        assert {f.filename for f in spec.files.files} == {
            "model.bin",
            "config.json",
            "tokenizer.json",
            "vocabulary.txt",
        }
        # The pins are the identity: the challenger's model.bin is NOT the
        # incumbent's.
        incumbent = CATALOG["whisper"].files
        assert incumbent is not None
        challenger_bin = next(f for f in spec.files.files if f.filename == "model.bin")
        incumbent_bin = next(f for f in incumbent.files if f.filename == "model.bin")
        assert challenger_bin.sha256 != incumbent_bin.sha256

    def test_an_undeclared_override_keeps_hosting_the_incumbent(self) -> None:
        (spec,) = build_slot_specs(Settings(slots="whisper"))
        assert spec.artifact == "whisper-small"
        assert spec.files is CATALOG["whisper"].files

    def test_an_unregistered_checkpoint_is_still_refused(self) -> None:
        # The M5 identity law survives admission: a declaration can select
        # a pinned identity, never invent one.
        with pytest.raises(ValueError, match="registered artifacts are"):
            specs("whisper:whisper-large-v3")

    def test_incumbent_and_challenger_may_share_one_research_process(self) -> None:
        # Not the production topology (one artifact per deployment,
        # F-M5-5) — but the mechanism must compose, and a future bridging
        # session may want both behind one /info.
        assert specs("whisper,whisper:whisper-base") == [
            ("default", "whisper-small"),
            ("whisper-base", "whisper-base"),
        ]
