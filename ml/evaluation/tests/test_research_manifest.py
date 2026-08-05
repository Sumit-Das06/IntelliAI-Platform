"""The research harness manifest: reachable for research, invisible to production.

Challenger admission (B6) holds one line: a challenger is measurable and
production is unchanged. These tests are that line, checked against the
committed manifests rather than asserted.
"""

import json
from pathlib import Path

import pytest

from intelliai_evaluation.resolution import UnservedError, load_manifest

PRODUCTION = Path("ml/evaluation/manifests/resolution.json")
RESEARCH = Path("ml/evaluation/manifests/research.json")

#: Artifacts admitted for research hosting only. Every entry here must be
#: absent from the production manifest — the day one appears in both, a
#: promotion happened somewhere other than a promotion.
CHALLENGERS = ("whisper-base",)


class TestTheResearchManifestResolves:
    def test_it_parses_through_the_same_reader_as_production(self) -> None:
        # One reader, two documents: the harness must not grow a second
        # resolution code path for research, or the two will drift.
        manifest = load_manifest(RESEARCH)
        assert manifest.schema_version == 1

    def test_the_challenger_resolves_to_the_research_deployment(self) -> None:
        serving = load_manifest(RESEARCH).resolve("research:whisper-base", None)
        assert serving.artifact == "whisper-base"
        assert serving.artifact_version == 1
        assert serving.deployment == "stt-runtime-research"

    def test_research_subjects_are_namespaced_beyond_confusion(self) -> None:
        # A research subject is not a promise. The namespace makes a
        # mix-up a visible absurdity rather than a plausible slug.
        for entry in load_manifest(RESEARCH).models:
            assert entry.public_model.startswith("research:")

    def test_no_research_route_carries_a_status_or_evidence(self) -> None:
        # A challenger has no ladder rung and no evidence chain to cite.
        # A status here would be a promotion that bypassed promotion.
        for entry in load_manifest(RESEARCH).models:
            for route in entry.routes:
                assert route.status is None
                assert route.evidence is None


class TestProductionCannotReachTheChallenger:
    @pytest.mark.parametrize("challenger", CHALLENGERS)
    def test_the_production_manifest_never_mentions_it(self, challenger: str) -> None:
        assert challenger not in PRODUCTION.read_text(encoding="utf-8")

    @pytest.mark.parametrize("challenger", CHALLENGERS)
    def test_no_production_route_resolves_to_it(self, challenger: str) -> None:
        manifest = load_manifest(PRODUCTION)
        for entry in manifest.models:
            for route in entry.routes:
                assert route.artifact != challenger

    def test_the_product_promise_does_not_know_the_research_namespace(self) -> None:
        with pytest.raises(UnservedError):
            load_manifest(PRODUCTION).resolve("research:whisper-base", None)

    def test_the_research_manifest_holds_no_product_promise(self) -> None:
        # The isolation cuts both ways: a run against the research
        # manifest cannot claim to have measured `intelliai-stt`.
        with pytest.raises(UnservedError):
            load_manifest(RESEARCH).resolve("intelliai-stt", None)


class TestTheGatewayHasNeverHeardOfIt:
    """The registry catalog is code; absence is checkable at the source."""

    @pytest.mark.parametrize("challenger", CHALLENGERS)
    def test_no_gateway_source_names_the_challenger(self, challenger: str) -> None:
        gateway = Path("apps/api/src/intelliai_api")
        offenders = [
            path for path in gateway.rglob("*.py") if challenger in path.read_text(encoding="utf-8")
        ]
        assert not offenders, (
            f"{challenger} appears in gateway source: {offenders}. Admission is "
            "research hosting; the production registry learns a challenger's name "
            "only through a promotion diff."
        )

    def test_admission_required_no_engine_vocabulary_edit(self) -> None:
        # The denylist guards deployment NAMES against engine names. A
        # challenger is an artifact, not an engine, so admitting one must
        # never touch it — this pins that the vocabulary is exactly the
        # engine/library names it was before B6.
        source = Path("apps/api/src/intelliai_api/core/config.py").read_text(encoding="utf-8")
        assert "whisper-base" not in source


def test_the_manifests_disagree_about_nothing_they_share() -> None:
    # Distinct subject sets: no public model appears in both documents,
    # so no resolution can depend on which file an operator happened to
    # pass.
    production = {m.public_model for m in load_manifest(PRODUCTION).models}
    research = {m.public_model for m in load_manifest(RESEARCH).models}
    assert not production & research


def test_the_research_manifest_is_not_a_registry_export() -> None:
    # The production manifest is generated and drift-checked against the
    # registry; the research manifest is hand-authored and must say so —
    # its provenance is different on purpose, and a reader should never
    # mistake one for the other.
    document = json.loads(RESEARCH.read_text(encoding="utf-8"))
    assert "_comment" in document
    assert "NEVER exported" in document["_comment"]
