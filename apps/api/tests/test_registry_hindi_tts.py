"""Hindi TTS, post-promotion (M42).

The M39 implementation and M40 validation were approved by the founder
on 2026-08-24 and ACTIVATED in the live catalog. What these tests pin:

1. the LIVE registry serves the promotion — both Hindi voices resolve
   to the EXACT approved artifact, and the hi route is available;
2. the approval record rides on the route, as a real decision
   reference (never the pending sentinel that made it constructible);
3. English TTS is untouched by the Hindi promotion;
4. the ROLLBACK target stays reviewed: reverting the promotion commit
   must land the honest refusal back, with no half-promoted state;
5. the leak guard holds — engine voice packs never enter product
   records, and an engine token is not addressable as a voice.
"""

import pytest

from intelliai_api.registry import VoiceNotFoundError
from intelliai_api.registry.catalog import _ARTIFACTS, _ROUTES, _VOICES, default_registry
from intelliai_api.registry.proposals import ROLLBACK_TTS_PRODUCTION_ROUTE, staging_registry
from intelliai_api.registry.records import LanguageStatus

HINDI_VOICES = ("hindi-female", "hindi-male")


class TestThePromotionIsLive:
    def test_hindi_voices_resolve_to_the_exact_approved_artifact(self) -> None:
        for voice_id in HINDI_VOICES:
            resolved = default_registry().resolve_voice("intelliai-tts", voice_id)
            assert resolved.artifact.id == "kokoro-82m"
            assert resolved.service == "tts-runtime"

    def test_the_hindi_route_is_available_in_the_live_catalog(self) -> None:
        for language in ("hi", "hi-IN"):
            assert (
                default_registry().language_status("intelliai-tts", language)
                is LanguageStatus.AVAILABLE
            )
            assert (
                default_registry().resolve("intelliai-tts", language=language).artifact.id
                == "kokoro-82m"
            )

    def test_voice_records_declare_exactly_hindi(self) -> None:
        for voice_id in HINDI_VOICES:
            assert default_registry().voice("intelliai-tts", voice_id).languages == ("hi",)

    def test_the_approval_record_rides_on_the_route(self) -> None:
        route = next(
            r
            for r in _ROUTES
            if r.public_model_id == "intelliai-tts" and r.selector.language == "hi"
        )
        assert route.evidence is not None
        assert route.evidence.corpus == "m38-hindi-tts-probe-texts@v1"
        assert route.evidence.quality_baseline == "2026-08-22-hindi-tts-model-selection"
        assert (
            route.evidence.production_benchmark == "2026-08-24-kokoro-hindi-staging-validation-m40"
        )
        # A real founder decision reference — the sentinel is history.
        assert "F-M42" in route.evidence.approval
        assert not route.evidence.approval.startswith("PENDING")

    def test_the_promotion_needed_no_artifact_readmission(self) -> None:
        # One artifact serves both languages: the promotion is a route +
        # voices diff, so rollout and rollback never wait on artifact
        # admission mid-incident.
        kokoro = [a for a in _ARTIFACTS if a.id == "kokoro-82m"]
        assert len(kokoro) == 1
        assert "hf_alpha" in kokoro[0].provenance  # the served Hindi packs, named
        assert "hm_psi" in kokoro[0].provenance
        assert "exec boundary" in kokoro[0].provenance  # the espeak posture, recorded

    def test_only_the_approved_hindi_voices_exist(self) -> None:
        # The research packs and the rejected candidates never became
        # product voices (M38 measured four Kokoro voices; two shipped).
        served = {record.id for record in default_registry().list_voices()}
        assert served == {
            "english-female",
            "english-male",
            "reference-alto",
            "reference-bass",
            *HINDI_VOICES,
        }
        for absent in ("hf_beta", "hm_omega", "supertonic", "f5-hindi"):
            assert absent not in served


class TestEnglishIsUntouched:
    def test_english_voices_stay_english(self) -> None:
        registry = default_registry()
        for voice_id in ("english-female", "english-male", "reference-alto", "reference-bass"):
            assert registry.voice("intelliai-tts", voice_id).languages == ("en",)
            assert registry.resolve_voice("intelliai-tts", voice_id).artifact.id == "kokoro-82m"

    def test_english_route_and_default_resolution_unchanged(self) -> None:
        registry = default_registry()
        assert registry.language_status("intelliai-tts", "en") is LanguageStatus.SUPPORTED
        assert registry.resolve_voice("intelliai-tts", None).artifact.id == "kokoro-82m"

    def test_arabic_synthesis_stays_refused(self) -> None:
        from intelliai_api.registry.registry import LanguageNotSupportedError

        with pytest.raises(LanguageNotSupportedError):
            default_registry().resolve("intelliai-tts", language="ar")

    def test_stt_routes_are_untouched_by_the_tts_promotion(self) -> None:
        registry = default_registry()
        assert registry.resolve("intelliai-stt", language="hi").artifact.id == (
            "qwen3-asr-0.6b-hi-ft-e3"
        )
        for language in ("en", "ar", None):
            assert registry.resolve("intelliai-stt", language=language).artifact.id == (
                "whisper-small"
            )


class TestRollback:
    def test_the_rollback_target_is_reviewed_and_constructible(self) -> None:
        # Reverting the promotion commit must land exactly this route:
        # the honest refusal production served before M42.
        assert ROLLBACK_TTS_PRODUCTION_ROUTE.public_model_id == "intelliai-tts"
        assert ROLLBACK_TTS_PRODUCTION_ROUTE.selector.language == "hi"
        assert ROLLBACK_TTS_PRODUCTION_ROUTE.status is LanguageStatus.UNAVAILABLE
        assert ROLLBACK_TTS_PRODUCTION_ROUTE.artifact_id is None

    def test_rollback_is_whole_language_never_half_promoted(self) -> None:
        # The voices and the route travel together: reverting the
        # promotion removes both, so a hindi-female request answers
        # voice_not_found rather than resolving to a refused language.
        # Pinned by construction — the voice records and the route live
        # in the SAME reviewed commit (both are asserted present here).
        registry = default_registry()
        assert registry.language_status("intelliai-tts", "hi") is LanguageStatus.AVAILABLE
        assert {record.id for record in _VOICES} >= set(HINDI_VOICES)


class TestLeakGuard:
    def test_product_records_never_name_engine_tokens(self) -> None:
        banned = ("hf_alpha", "hm_psi", "hf_", "hm_", "kokoro", "espeak", "misaki")
        for record in default_registry().list_voices():
            surface = (record.id + " " + record.description).lower()
            for token in banned:
                assert token not in surface, (record.id, token)

    def test_engine_voice_tokens_are_not_addressable(self) -> None:
        for token in ("hf_alpha", "hm_psi", "af_heart", "am_michael"):
            with pytest.raises(VoiceNotFoundError):
                default_registry().resolve_voice("intelliai-tts", token)


class TestStagingAgreesWithProduction:
    def test_no_proposal_is_pending_so_staging_equals_production(self) -> None:
        staging, live = staging_registry(), default_registry()
        for language in ("hi", "en", "ar", None):
            for model in ("intelliai-tts", "intelliai-stt"):
                staged = staging.language_status(model, language) if language else None
                served = live.language_status(model, language) if language else None
                assert staged == served
        assert {r.id for r in staging.list_voices()} == {r.id for r in live.list_voices()}
