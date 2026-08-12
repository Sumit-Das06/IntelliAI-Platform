"""The prepared-but-disabled catalog change (Milestone 17, Phases 8-9).

Three guarantees, each load-bearing for the canary plan:
1. the proposal VALIDATES — activation is a small diff, not a design
   session under incident pressure;
2. the LIVE registry is untouched — Hindi still resolves to the
   incumbent until the promotion commit lands;
3. a promotion cannot ship the pending-approval sentinel — the founder
   decision must physically replace it.
"""

from intelliai_api.registry.catalog import _ARTIFACTS, _MODELS, _ROUTES, _VOICES, default_registry
from intelliai_api.registry.proposals import (
    APPROVAL_PENDING,
    QWEN3_ASR_ARTIFACT,
    QWEN3_HI_EVIDENCE,
    QWEN3_HINDI_ROUTE,
    ROLLBACK_HINDI_ROUTE,
)
from intelliai_api.registry.registry import Registry


class TestTheProposalIsActivatable:
    def test_a_registry_built_with_the_proposal_composes(self) -> None:
        # The EXACT promotion diff, rehearsed: add the artifact, swap the
        # hi route. If this ever fails, the proposal has drifted from the
        # catalog's rules and must be repaired BEFORE anyone needs it.
        routes = tuple(
            QWEN3_HINDI_ROUTE
            if (route.public_model_id == "intelliai-stt" and route.selector.language == "hi")
            else route
            for route in _ROUTES
        )
        promoted = Registry(
            artifacts=(*_ARTIFACTS, QWEN3_ASR_ARTIFACT),
            models=_MODELS,
            voices=_VOICES,
            routes=routes,
        )
        assert promoted.resolve("intelliai-stt", language="hi").artifact.id == "qwen3-asr-0.6b"
        # Every other language keeps the incumbent through the same build.
        assert promoted.resolve("intelliai-stt", language="en").artifact.id == "whisper-small"
        assert promoted.resolve("intelliai-stt", language=None).artifact.id == "whisper-small"

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
        # Phase 9's gate: no promotion without an attached benchmark
        # baseline. The evidence rides ON the route record itself.
        assert QWEN3_HINDI_ROUTE.evidence is QWEN3_HI_EVIDENCE
        assert QWEN3_HI_EVIDENCE.corpus == "stt-hi-public-eval@v1"
        assert QWEN3_HI_EVIDENCE.quality_baseline.startswith("2026-08-12-research-qwen3")
        assert QWEN3_HI_EVIDENCE.production_benchmark.startswith("2026-08-12-qwen3")


class TestTheLiveRegistryIsUntouched:
    def test_hindi_still_resolves_to_the_incumbent(self) -> None:
        resolved = default_registry().resolve("intelliai-stt", language="hi")
        assert resolved.artifact.id == "whisper-small"

    def test_the_candidate_artifact_is_not_registered(self) -> None:
        assert all(artifact.id != "qwen3-asr-0.6b" for artifact in _ARTIFACTS)
        assert all(route.artifact_id != "qwen3-asr-0.6b" for route in _ROUTES)

    def test_no_live_evidence_carries_the_pending_sentinel(self) -> None:
        # The sentinel exists to be REPLACED by the founder decision; a
        # live catalog carrying it would be a promotion that skipped the
        # decision. This test makes that shortcut impossible to merge —
        # activating the proposal forces editing the approval field.
        for route in _ROUTES:
            if route.evidence is not None:
                assert not route.evidence.approval.startswith("PENDING"), route
        assert APPROVAL_PENDING.startswith("PENDING")
