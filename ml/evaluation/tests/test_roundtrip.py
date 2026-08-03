"""Round-trip metrics: Unicode-honest normalization, WER, trap scoring."""

from intelliai_evaluation.roundtrip import (
    pronunciation_accuracy,
    round_trip_wer,
    speech_normalize,
)


class TestSpeechNormalize:
    def test_english_basics(self) -> None:
        assert speech_normalize("Hello, World! Don't stop.") == ["hello", "world", "don't", "stop"]

    def test_devanagari_survives_completely(self) -> None:
        # Matras (combining marks) must survive — the STT ruler's ASCII
        # normalization would erase them; this one must not.
        tokens = speech_normalize("विद्यार्थी ने प्रश्न का उत्तर स्पष्ट शब्दों में लिखा।")
        assert tokens[0] == "विद्यार्थी"
        assert "प्रश्न" in tokens
        assert not any("।" in token for token in tokens)  # danda separates, never survives

    def test_mixed_hinglish(self) -> None:
        tokens = speech_normalize("Meeting के बाद report भेज देना, please।")
        assert tokens == ["meeting", "के", "बाद", "report", "भेज", "देना", "please"]

    def test_digits_survive(self) -> None:
        assert speech_normalize("Train 12951 at 9:45") == ["train", "12951", "at", "9", "45"]

    def test_nfc_composition_makes_equal_forms_equal(self) -> None:
        composed = "क़"  # single codepoint U+0958
        decomposed = "क़"  # KA + nukta
        assert speech_normalize(composed) == speech_normalize(decomposed)


class TestRoundTripWer:
    def test_perfect_round_trip(self) -> None:
        text = "कल हम बाज़ार जाकर सब्ज़ियाँ और फल खरीदेंगे।"
        breakdown = round_trip_wer(text, text)
        assert breakdown.wer == 0.0

    def test_the_founder_case(self) -> None:
        # The first real wedge measurement: लगता transcribed as लकता.
        reference = "मुझे तुमसे बात करके बहुत अच्छा लगता है"
        transcript = "मुझे तुमसे बात करके बहुत अच्छा लकता है"
        breakdown = round_trip_wer(reference, transcript)
        assert breakdown.substitutions == 1
        assert breakdown.wer == 1 / 8

    def test_punctuation_and_case_are_forgiven(self) -> None:
        assert round_trip_wer("Hello, world!", "hello world").wer == 0.0


class TestPronunciationAccuracy:
    def test_all_traps_survive(self) -> None:
        assert pronunciation_accuracy(("API", "HTTP"), "the api gateway speaks http") == 1.0

    def test_partial_survival(self) -> None:
        assert pronunciation_accuracy(("ज्ञान", "उत्कृष्टता"), "ज्ञान से सब होता है") == 0.5

    def test_multi_token_trap_must_survive_contiguously(self) -> None:
        # "careers@example.com" normalizes to three tokens; scattered
        # fragments are not a hit.
        trap = ("careers@example.com",)
        assert pronunciation_accuracy(trap, "send it to careers example com today") == 1.0
        assert pronunciation_accuracy(trap, "careers page on example site dot com") == 0.0

    def test_no_traps_is_none_not_perfect(self) -> None:
        assert pronunciation_accuracy((), "anything") is None

    def test_number_trap(self) -> None:
        assert pronunciation_accuracy(("12951",), "ट्रेन 12951 समय पर है") == 1.0
