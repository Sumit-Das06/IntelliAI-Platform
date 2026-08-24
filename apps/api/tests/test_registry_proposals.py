"""The promotion module, post-activation (M26).

The E3 Hindi promotion was approved by the founder on 2026-08-19 and
activated in the live catalog. What these tests pin now:

1. the LIVE registry serves the promotion — Hindi resolves to the
   EXACT approved artifact, English/default keep the incumbent;
2. the approval record rides on the route — and it is a real decision
   reference, never the pending sentinel;
3. the ROLLBACK target stays reviewed and constructible: reverting the
   promotion commit must land Hindi back on whisper-small, whose
   artifact is still registered (no re-admission needed);
4. the staging profile composes the live catalog plus prepared
   proposals — for TRANSCRIPTION it must agree with production on
   every route (the M39 pending proposal touches synthesis only; its
   own suite is test_registry_hindi_tts.py).
"""

import pytest

from intelliai_api.core.config import Settings
from intelliai_api.registry.catalog import _ARTIFACTS, _ROUTES, default_registry
from intelliai_api.registry.proposals import ROLLBACK_HINDI_ROUTE, staging_registry

E3 = "qwen3-asr-0.6b-hi-ft-e3"


class TestThePromotionIsLive:
    def test_hindi_resolves_to_the_exact_approved_artifact(self) -> None:
        for language in ("hi", "hi-IN"):
            resolved = default_registry().resolve("intelliai-stt", language=language)
            assert resolved.artifact.id == E3
            assert resolved.artifact.version == 1

    def test_english_and_default_keep_the_incumbent(self) -> None:
        assert default_registry().resolve("intelliai-stt", language="en").artifact.id == (
            "whisper-small"
        )
        assert default_registry().resolve("intelliai-stt", language=None).artifact.id == (
            "whisper-small"
        )
        assert default_registry().resolve("intelliai-stt", language="ar").artifact.id == (
            "whisper-small"
        )

    def test_the_approved_artifact_identity_is_exact(self) -> None:
        # The promotion names THIS fine-tune — never the generic base,
        # E1, E2, or anything mutable. The provenance pins the chain the
        # founder approved.
        artifact = next(a for a in _ARTIFACTS if a.id == E3)
        assert artifact.version == 1
        assert "e54586c4" in artifact.provenance  # export sha
        assert "6cfc585d" in artifact.provenance  # training manifest sha
        assert "5eb144179a02acc5e5ba31e748d22b0cf3e303b0" in artifact.provenance  # base rev
        assert "checkpoint-1500" in artifact.provenance
        assert "b10344" in artifact.provenance  # runtime pin
        assert "41a342b5" in artifact.provenance  # official mmproj
        forbidden = {"qwen3-asr-0.6b-hi-ft-e1", "qwen3-asr-0.6b-hi-ft-e2"}
        assert not any(a.id in forbidden for a in _ARTIFACTS)

    def test_the_approval_record_rides_on_the_route(self) -> None:
        route = next(
            r
            for r in _ROUTES
            if r.public_model_id == "intelliai-stt" and r.selector.language == "hi"
        )
        assert route.evidence is not None
        assert route.evidence.corpus == "stt-hi-public-eval@v1"
        assert route.evidence.quality_baseline == (
            "2026-08-18-research-qwen3-asr-0.6b-hi-ft-e3-hi-m23"
        )
        assert route.evidence.production_benchmark == "2026-08-18-qwen3-e3-cpu-ladder"
        # A real founder decision reference — the sentinel is history.
        assert "F-M26" in route.evidence.approval
        assert not route.evidence.approval.startswith("PENDING")

    def test_no_live_evidence_carries_a_pending_sentinel(self) -> None:
        for route in _ROUTES:
            if route.evidence is not None:
                assert not route.evidence.approval.startswith("PENDING"), route


class TestRollback:
    def test_the_rollback_target_is_reviewed_and_constructible(self) -> None:
        # Rollback = git revert of the promotion commit; its result must
        # equal this record: Hindi back on the incumbent, same status
        # rung, and the incumbent artifact still registered so no
        # re-admission is ever needed mid-incident.
        assert ROLLBACK_HINDI_ROUTE.artifact_id == "whisper-small"
        assert any(a.id == "whisper-small" for a in _ARTIFACTS)
        live_hi = next(
            r
            for r in _ROUTES
            if r.public_model_id == "intelliai-stt" and r.selector.language == "hi"
        )
        assert ROLLBACK_HINDI_ROUTE.status == live_hi.status
        assert ROLLBACK_HINDI_ROUTE.selector == live_hi.selector


class TestStagingProfile:
    def test_staging_agrees_with_production_on_every_stt_route(self) -> None:
        # The pending M39 proposal touches SYNTHESIS only: for STT,
        # staging and production must agree on every route, or a shape
        # would serve something unreviewed.
        staging = staging_registry()
        live = default_registry()
        for language in ("hi", "hi-IN", "en", "ar", None):
            assert (
                staging.resolve("intelliai-stt", language=language).artifact.id
                == live.resolve("intelliai-stt", language=language).artifact.id
            )

    def test_the_default_profile_is_production(self) -> None:
        assert Settings.model_fields["registry_profile"].default == "production"

    def test_staging_is_refused_under_prod_env(self) -> None:
        with pytest.raises(ValueError, match=r"reviewed\s+promotion commit"):
            Settings(env="prod", registry_profile="staging")
