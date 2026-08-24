"""M39 — the Hindi TTS staging proposal, and the production refusal it
must never touch.

The M24 mechanism, applied to synthesis: the staging profile composes
the two M38-approved Hindi voices and flips `intelliai-tts x hi` to the
kokoro-82m artifact; the LIVE catalog keeps its honest refusal until a
separate production promotion commit. These tests pin both sides and
the leak-guard (engine pack tokens never enter product records).
"""

import pytest

from intelliai_api.registry import VoiceNotFoundError
from intelliai_api.registry.catalog import default_registry
from intelliai_api.registry.proposals import (
    APPROVAL_PENDING,
    HINDI_TTS_ROUTE,
    HINDI_TTS_VOICES,
    staging_registry,
)
from intelliai_api.registry.records import LanguageStatus
from intelliai_api.registry.registry import LanguageNotSupportedError


class TestProductionStaysRefusing:
    def test_live_catalog_has_no_hindi_voice(self) -> None:
        for voice_id in ("hindi-female", "hindi-male"):
            with pytest.raises(VoiceNotFoundError):
                default_registry().resolve_voice("intelliai-tts", voice_id)

    def test_live_hindi_tts_route_is_still_unavailable(self) -> None:
        assert (
            default_registry().language_status("intelliai-tts", "hi") is LanguageStatus.UNAVAILABLE
        )

    def test_live_voice_listing_is_english_only(self) -> None:
        for record in default_registry().list_voices():
            assert record.languages == ("en",)

    def test_the_proposal_carries_the_pending_sentinel(self) -> None:
        # Constructible ONLY in pending form; the production promotion
        # diff must replace it with the founder decision reference.
        assert HINDI_TTS_ROUTE.evidence is not None
        assert HINDI_TTS_ROUTE.evidence.approval == APPROVAL_PENDING
        assert APPROVAL_PENDING.startswith("PENDING")


class TestStagingServesTheProposal:
    def test_hindi_voices_resolve_to_the_incumbent_artifact(self) -> None:
        for voice_id in ("hindi-female", "hindi-male"):
            resolved = staging_registry().resolve_voice("intelliai-tts", voice_id)
            assert resolved.artifact.id == "kokoro-82m"
            assert resolved.service == "tts-runtime"

    def test_the_hindi_route_is_available_in_staging(self) -> None:
        assert staging_registry().language_status("intelliai-tts", "hi") is LanguageStatus.AVAILABLE

    def test_voice_records_declare_exactly_hindi(self) -> None:
        staging = staging_registry()
        for voice_id in ("hindi-female", "hindi-male"):
            record = staging.voice("intelliai-tts", voice_id)
            assert record.languages == ("hi",)

    def test_english_voices_stay_english_everywhere(self) -> None:
        # Adding Hindi must not make any English voice bilingual.
        staging = staging_registry()
        for voice_id in ("english-female", "english-male", "reference-alto", "reference-bass"):
            assert staging.voice("intelliai-tts", voice_id).languages == ("en",)
            resolved = staging.resolve_voice("intelliai-tts", voice_id)
            assert resolved.artifact.id == "kokoro-82m"

    def test_default_voice_resolution_is_unchanged(self) -> None:
        assert staging_registry().resolve_voice("intelliai-tts", None).artifact.id == "kokoro-82m"

    def test_arabic_stays_refused_in_staging_too(self) -> None:
        with pytest.raises(LanguageNotSupportedError):
            staging_registry().resolve("intelliai-tts", language="ar")

    def test_stt_routes_are_untouched_by_the_tts_proposal(self) -> None:
        staging, live = staging_registry(), default_registry()
        for language in ("hi", "en", "ar", None):
            assert (
                staging.resolve("intelliai-stt", language=language).artifact.id
                == live.resolve("intelliai-stt", language=language).artifact.id
            )


class TestLeakGuard:
    def test_product_records_never_name_engine_tokens(self) -> None:
        banned = ("hf_alpha", "hm_psi", "hf_", "hm_", "kokoro", "espeak", "misaki")
        for record in HINDI_TTS_VOICES:
            surface = (record.id + " " + record.description).lower()
            for token in banned:
                assert token not in surface, (record.id, token)

    def test_the_voice_ids_are_the_approved_product_names(self) -> None:
        assert tuple(record.id for record in HINDI_TTS_VOICES) == (
            "hindi-female",
            "hindi-male",
        )
