"""The prepared-but-disabled catalog change (M17 mechanism, M24 candidate).

Three guarantees, each load-bearing for the canary plan:
1. the proposal VALIDATES — activation is a small diff, not a design
   session under incident pressure;
2. the LIVE registry is untouched — Hindi still resolves to the
   incumbent until the promotion commit lands;
3. a promotion cannot ship the pending-approval sentinel — the founder
   decision must physically replace it.

Milestone 24: the proposed candidate is the E3-SPECIFIC fine-tune
`qwen3-asr-0.6b-hi-ft-e3` — never the generic base artifact, which was
the superseded M17 proposal and must not be confusable with E3.
"""

import pytest

from intelliai_api.core.config import Settings
from intelliai_api.registry.catalog import _ARTIFACTS, _MODELS, _ROUTES, _VOICES, default_registry
from intelliai_api.registry.proposals import (
    APPROVAL_PENDING,
    QWEN3_E3_ARTIFACT,
    QWEN3_E3_HI_EVIDENCE,
    QWEN3_E3_HINDI_ROUTE,
    ROLLBACK_HINDI_ROUTE,
    staging_registry,
)
from intelliai_api.registry.registry import Registry

E3 = "qwen3-asr-0.6b-hi-ft-e3"


class TestTheProposalIsActivatable:
    def test_a_registry_built_with_the_proposal_composes(self) -> None:
        # The EXACT promotion diff, rehearsed: add the artifact, swap the
        # hi route. If this ever fails, the proposal has drifted from the
        # catalog's rules and must be repaired BEFORE anyone needs it.
        routes = tuple(
            QWEN3_E3_HINDI_ROUTE
            if (route.public_model_id == "intelliai-stt" and route.selector.language == "hi")
            else route
            for route in _ROUTES
        )
        promoted = Registry(
            artifacts=(*_ARTIFACTS, QWEN3_E3_ARTIFACT),
            models=_MODELS,
            voices=_VOICES,
            routes=routes,
        )
        assert promoted.resolve("intelliai-stt", language="hi").artifact.id == E3
        # Every other language keeps the incumbent through the same build.
        assert promoted.resolve("intelliai-stt", language="en").artifact.id == "whisper-small"
        assert promoted.resolve("intelliai-stt", language=None).artifact.id == "whisper-small"

    def test_the_proposal_is_e3_specific_never_the_generic_base(self) -> None:
        # M24 law: E3 must not be confusable with base/E1/E2. The route
        # and artifact name the fine-tune EXACTLY; the superseded base
        # proposal is gone from this module.
        assert QWEN3_E3_HINDI_ROUTE.artifact_id == E3
        assert QWEN3_E3_ARTIFACT.id == E3
        assert "e54586c4" in QWEN3_E3_ARTIFACT.provenance  # the E3 model sha
        assert "6cfc585d" in QWEN3_E3_ARTIFACT.provenance  # the v3 corpus sha
        assert "checkpoint-1500" in QWEN3_E3_ARTIFACT.provenance

    def test_the_rollback_target_is_todays_live_route(self) -> None:
        # Rollback = git revert; its result must equal what serves today.
        live_hi = next(
            route
            for route in _ROUTES
            if route.public_model_id == "intelliai-stt" and route.selector.language == "hi"
        )
        assert ROLLBACK_HINDI_ROUTE.artifact_id == live_hi.artifact_id == "whisper-small"
        assert ROLLBACK_HINDI_ROUTE.status == live_hi.status

    def test_the_baseline_is_attached_and_versioned(self) -> None:
        # No promotion without an attached benchmark baseline. The
        # evidence rides ON the route record itself and cites the M23
        # adapter-side record + the M24 concurrency ladder.
        assert QWEN3_E3_HINDI_ROUTE.evidence is QWEN3_E3_HI_EVIDENCE
        assert QWEN3_E3_HI_EVIDENCE.corpus == "stt-hi-public-eval@v1"
        assert QWEN3_E3_HI_EVIDENCE.quality_baseline == (
            "2026-08-18-research-qwen3-asr-0.6b-hi-ft-e3-hi-m23"
        )
        assert QWEN3_E3_HI_EVIDENCE.production_benchmark.startswith("2026-08-18-qwen3-e3")


class TestStagingProfile:
    """Milestone 18: the ONLY sanctioned path from gateway to candidate."""

    def test_staging_registry_routes_hindi_to_the_candidate(self) -> None:
        staging = staging_registry()
        assert staging.resolve("intelliai-stt", language="hi").artifact.id == E3
        # Everything else keeps the incumbent — the switch is per-language.
        assert staging.resolve("intelliai-stt", language="en").artifact.id == "whisper-small"
        assert staging.resolve("intelliai-stt", language=None).artifact.id == "whisper-small"
        assert staging.resolve("intelliai-stt", language="ar").artifact.id == "whisper-small"

    def test_the_default_profile_is_production(self) -> None:
        # A gateway started with no configuration composes the reviewed
        # catalog. Staging is an explicit, loud choice — never a default.
        assert Settings.model_fields["registry_profile"].default == "production"

    def test_staging_is_refused_under_prod_env(self) -> None:
        with pytest.raises(ValueError, match=r"reviewed\s+promotion commit"):
            Settings(env="prod", registry_profile="staging")


class TestTheLiveRegistryIsUntouched:
    def test_hindi_still_resolves_to_the_incumbent(self) -> None:
        resolved = default_registry().resolve("intelliai-stt", language="hi")
        assert resolved.artifact.id == "whisper-small"

    def test_the_candidate_artifact_is_not_registered(self) -> None:
        # Neither the E3 candidate nor the superseded base challenger may
        # appear anywhere in the LIVE catalog.
        for challenger in (E3, "qwen3-asr-0.6b"):
            assert all(artifact.id != challenger for artifact in _ARTIFACTS)
            assert all(route.artifact_id != challenger for route in _ROUTES)

    def test_no_live_evidence_carries_the_pending_sentinel(self) -> None:
        # The sentinel exists to be REPLACED by the founder decision; a
        # live catalog carrying it would be a promotion that skipped the
        # decision. This test makes that shortcut impossible to merge —
        # activating the proposal forces editing the approval field.
        for route in _ROUTES:
            if route.evidence is not None:
                assert not route.evidence.approval.startswith("PENDING"), route
        assert APPROVAL_PENDING.startswith("PENDING")
