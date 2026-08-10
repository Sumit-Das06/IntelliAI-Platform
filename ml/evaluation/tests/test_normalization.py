"""Normalization profiles: the ruler, pinned and versioned."""

import unicodedata

import pytest

from intelliai_evaluation.normalization import (
    ASCII_EN_V1,
    LANGUAGE_PROFILES,
    PROFILES,
    UNICODE_GENERIC_V1,
    UNICODE_GENERIC_V2,
    DuplicateProfileError,
    InvalidProfileError,
    NormalizationRegistry,
    ProfileNotRegisteredError,
    profile_for,
    unicode_profile,
)
from intelliai_evaluation.roundtrip import speech_normalize
from intelliai_evaluation.wer import normalize_words

ZWNJ = "‌"
ZWJ = "‍"

# Devanagari
KSHA = "क्ष"  # क्ष, one conjunct
HINDI = "मुझे हिंदी आती है"
DANDA = "।"
NUKTA_COMPOSED = "क़"  # क़
NUKTA_DECOMPOSED = "क़"  # क + ़

# Arabic
KATABA_VOWELLED = "كَتَبَ"  # كَتَبَ
KATABA_BARE = "كتب"  # كتب


def test_the_registry_holds_exactly_three_rulers() -> None:
    """Golden pin. Arabic is deliberately absent — see the module docstring."""
    assert PROFILES.identities() == ("ascii_en@v1", "unicode_generic@v1", "unicode_generic@v2")


class TestAsciiEnV1IsFrozen:
    """The legacy anchor. Every committed English number rests on it."""

    def test_it_is_normalize_words_itself(self) -> None:
        for text in ("Hello, World!", "don't", "ASK NOT what your country", "", "  "):
            assert ASCII_EN_V1.words(text) == normalize_words(text)

    def test_it_erases_non_latin_text_which_is_why_it_is_english_only(self) -> None:
        # Not a defect to fix here: fixing it would change every committed
        # English number. It is why binding a language to a ruler is a
        # decision somebody has to make rather than a default.
        assert ASCII_EN_V1.words(HINDI) == []
        assert ASCII_EN_V1.words(KATABA_BARE) == []


class TestUnicodeGenericV1IsFrozenWithItsDefect:
    """@v1 pins the ruler behind the committed kokoro round_trip_wer."""

    def test_it_is_speech_normalize_itself(self) -> None:
        for text in ("Hello, World!", "don't", HINDI, KATABA_VOWELLED, KSHA, "", "  "):
            assert UNICODE_GENERIC_V1.words(text) == speech_normalize(text)

    def test_format_characters_split_a_word_in_two(self) -> None:
        # The defect, pinned rather than fixed: it is what the committed
        # synthesis baselines were measured with, and a released profile
        # version may never change its meaning.
        assert len(UNICODE_GENERIC_V1.words(f"क्{ZWNJ}ष")) == 2
        assert len(UNICODE_GENERIC_V1.words(KSHA)) == 1


class TestUnicodeGenericV2CorrectsIt:
    def test_format_characters_no_longer_split_words(self) -> None:
        for joiner in (ZWNJ, ZWJ):
            spelled = f"क्{joiner}ष"
            assert UNICODE_GENERIC_V2.words(spelled) == UNICODE_GENERIC_V2.words(KSHA)

    def test_the_fix_is_script_agnostic_which_is_why_it_is_not_language_named(self) -> None:
        # A profile is an evidence object, not a language object. The same
        # correction is right for Arabic, and will be inherited by the
        # Arabic profile when its fold table is ratified.
        assert UNICODE_GENERIC_V2.words(f"م{ZWNJ}ن") == UNICODE_GENERIC_V2.words("من")

    def test_matras_survive_because_they_are_word_content(self) -> None:
        # Category Mn, kept. Stripping category M to de-diacritise Arabic
        # would destroy exactly this.
        assert UNICODE_GENERIC_V2.words(HINDI) == HINDI.split()
        tokens = "".join(UNICODE_GENERIC_V2.words(HINDI))
        assert any(unicodedata.category(ch) == "Mn" for ch in tokens)

    def test_nfc_converges_the_two_nukta_spellings_so_no_rule_is_needed(self) -> None:
        assert UNICODE_GENERIC_V2.words(NUKTA_COMPOSED) == UNICODE_GENERIC_V2.words(
            NUKTA_DECOMPOSED
        )

    def test_danda_separates_words_without_becoming_one(self) -> None:
        assert UNICODE_GENERIC_V2.words(f"नमस्ते{DANDA}") == ["नमस्ते"]

    def test_it_differs_from_v1_by_exactly_the_format_rule(self) -> None:
        # Everything else must be identical, or "@v2 corrects @v1" would be
        # a claim rather than a description.
        for text in ("Hello, World!", "don't", HINDI, KATABA_VOWELLED, KSHA, "", "  "):
            assert UNICODE_GENERIC_V2.words(text) == UNICODE_GENERIC_V1.words(text)


class TestArabicIsNotMeasurableYetAndSaysSo:
    """No Arabic ruler is invented before an Arabic corpus or a verifier."""

    def test_no_arabic_profile_is_registered(self) -> None:
        assert not [p for p in PROFILES if "arabic" in p.name]

    def test_no_language_is_bound_to_arabic(self) -> None:
        with pytest.raises(ProfileNotRegisteredError, match="no normalization profile"):
            profile_for("ar")

    def test_the_generic_ruler_would_score_arabic_wrongly_which_is_the_point(self) -> None:
        # Vowelled and bare spellings of one word do not match: tashkeel is
        # Mn and survives. Folding it needs an enumerated table and a
        # native verifier, so the ruler does not exist rather than existing
        # and being wrong.
        assert UNICODE_GENERIC_V2.words(KATABA_VOWELLED) != UNICODE_GENERIC_V2.words(KATABA_BARE)


class TestLanguageBindingIsPolicyNotIdentity:
    def test_several_languages_share_one_profile(self) -> None:
        assert profile_for("en") is profile_for("hi") is UNICODE_GENERIC_V2

    def test_no_linguistic_content_is_bound_to_the_generic_ruler(self) -> None:
        # Ruled at PH0: a zxx slice measures hallucination, and counting
        # emitted words needs a tokenizer honest for any script they might
        # arrive in. A zxx slice carries no reference text, so no reference
        # can ever be scored under this binding.
        assert profile_for("zxx") is UNICODE_GENERIC_V2

    def test_mandarin_is_bound_to_the_generic_ruler(self) -> None:
        # Bound at 15B (founder-ordered zh evaluation). cer_unicode is the
        # primary zh ruler; the generic character stream is honest for Han
        # text. wer_unicode stays recordable but a whitespace "word" in
        # unsegmented zh is a sentence — never cite it for zh.
        assert profile_for("zh") is UNICODE_GENERIC_V2

    def test_an_unbound_language_refuses_rather_than_defaulting(self) -> None:
        # Defaulting is how a Devanagari reference gets scored by an ASCII
        # ruler and committed to an append-only ledger.
        with pytest.raises(ProfileNotRegisteredError):
            profile_for("ta")

    def test_the_binding_names_registered_profiles(self) -> None:
        for profile in LANGUAGE_PROFILES.values():
            assert PROFILES.get(profile.id) is profile


class TestReleasedVersionsAreImmutable:
    def test_redefining_a_released_identity_is_refused(self) -> None:
        registry = NormalizationRegistry()
        registry.register(unicode_profile(name="p", version=1, description="first"))
        with pytest.raises(DuplicateProfileError, match="released versions are immutable"):
            registry.register(unicode_profile(name="p", version=1, description="second"))

    def test_the_next_version_is_how_a_ruler_is_corrected(self) -> None:
        registry = NormalizationRegistry()
        registry.register(unicode_profile(name="p", version=1, description="first"))
        registry.register(unicode_profile(name="p", version=2, description="corrected"))
        assert registry.identities() == ("p@v1", "p@v2")

    def test_a_record_citing_an_unknown_ruler_cannot_be_reproduced(self) -> None:
        with pytest.raises(ProfileNotRegisteredError, match="unknown normalization profile"):
            PROFILES.require("devanagari@v1")


class TestCategoryFoldsAreRefused:
    """Arabic tashkeel and Devanagari matras are both Mn.

    A profile that strips category M to de-diacritise Arabic destroys
    Hindi, so folds are an enumerated codepoint table and a rule is not
    expressible here.
    """

    @pytest.mark.parametrize("category", ["M", "Mn", "L", "Cf", "Po"])
    def test_a_fold_keyed_on_a_unicode_category_is_refused(self, category: str) -> None:
        registry = NormalizationRegistry()
        with pytest.raises(InvalidProfileError, match="Unicode general"):
            registry.register(
                unicode_profile(
                    name="bad", version=1, description="x", codepoint_folds={category: ""}
                )
            )

    def test_a_multi_character_fold_key_is_refused(self) -> None:
        registry = NormalizationRegistry()
        with pytest.raises(InvalidProfileError, match="single codepoint"):
            registry.register(
                unicode_profile(
                    name="bad", version=1, description="x", codepoint_folds={"tashkeel": ""}
                )
            )

    def test_an_enumerated_codepoint_fold_is_accepted(self) -> None:
        """The shape the Arabic profile will take when it is ratified.

        Written as escapes, not literals: alef-with-hamza and bare alef are
        indistinguishable in most fonts, and a fold table is exactly the
        place where "which codepoint did you mean" must not be a guess.
        """
        alef = "\u0627"
        alef_hamza = "\u0623"
        alef_hamza_below = "\u0625"
        haa_meem_dal = "\u062d\u0645\u062f"
        registry = NormalizationRegistry()
        folded = registry.register(
            unicode_profile(
                name="demo",
                version=1,
                description="fold alef variants to bare alef",
                codepoint_folds={alef_hamza: alef, alef_hamza_below: alef},
            )
        )
        assert folded.words(alef_hamza + haa_meem_dal) == folded.words(alef + haa_meem_dal)

    def test_folds_cannot_be_edited_after_registration(self) -> None:
        with pytest.raises(TypeError):
            UNICODE_GENERIC_V2.codepoint_folds["x"] = "y"  # type: ignore[index]


class TestCharacterGranularity:
    def test_characters_are_derived_from_the_same_tokens_as_words(self) -> None:
        # CER and WER can never disagree about what the text was.
        assert UNICODE_GENERIC_V2.characters("Hello, World!") == list("hello world")

    def test_the_inter_word_space_counts_as_one_character(self) -> None:
        assert UNICODE_GENERIC_V2.characters("a b") == ["a", " ", "b"]
