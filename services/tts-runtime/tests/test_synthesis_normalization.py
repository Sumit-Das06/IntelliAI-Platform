"""M35 text-normalization laws: deterministic, idempotent, speech-only,
and surgically scoped — every rule proven, everything else untouched."""

import pytest

from intelliai_tts_runtime.normalization import normalize_for_speech
from intelliai_tts_runtime.pipeline import TextPipeline


class TestRules:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            # Slash dates (DD/MM/YYYY, the documented Indian convention).
            ("Your warranty expires on 12/08/2026.", "Your warranty expires on 12 August 2026."),
            ("Due 1/1/2027 sharp.", "Due 1 January 2027 sharp."),
            # MM/DD input that only parses the other way still speaks.
            ("Filed 08/25/2026 in court.", "Filed 25 August 2026 in court."),
            # Currency.
            (
                "The subscription costs $4.99 per month.",
                ("The subscription costs 4 dollars and 99 cents per month."),
            ),
            ("A flat $5 fee applies.", "A flat 5 dollars fee applies."),
            ("Pay ₹12,500 by Friday.", "Pay 12500 rupees by Friday."),
            ("Exactly $1 today.", "Exactly 1 dollar today."),
            # Percent.
            (
                "A late fee of 2.5% applies, and 25% is waived.",
                ("A late fee of 2.5 percent applies, and 25 percent is waived."),
            ),
            # Phone-style digit groups.
            (
                "Call +91 98765 43210 now.",
                "Call plus nine one, nine eight seven six five, four three two one zero now.",
            ),
            (
                "Reach us at 1800 425 9090 today.",
                "Reach us at one eight zero zero, four two five, nine zero nine zero today.",
            ),
        ],
    )
    def test_each_documented_rule(self, text: str, expected: str) -> None:
        assert normalize_for_speech(text).text == expected

    @pytest.mark.parametrize(
        "untouched",
        [
            "Hello, Sumit.",  # names are never our business
            "Priya Sharma spoke with Rajesh Iyer.",
            "The invoice total is 1247 dollars for 38 units.",  # plain numbers stay
            "The meeting is on August 3, 2026, at half past ten.",  # spoken dates stay
            "Reference number is 88231.",  # single number, not a phone
            "The API gateway routes requests over HTTP.",
        ],
    )
    def test_out_of_scope_text_passes_byte_identical(self, untouched: str) -> None:
        result = normalize_for_speech(untouched)
        assert result.text == untouched
        assert result.rule_hits == {}

    def test_idempotent_by_construction(self) -> None:
        # Expansions produce plain words no rule matches again: running
        # the normalizer on its own output changes nothing (the
        # no-double-expansion law).
        text = "Pay $4.99 (2.5% late fee) on 12/08/2026 or call +91 98765 43210."
        once = normalize_for_speech(text).text
        assert normalize_for_speech(once).text == once

    def test_rule_hits_are_counted(self) -> None:
        hits = normalize_for_speech("Pay $5 or 25% now, then $6.").rule_hits
        assert hits == {"dollars": 2, "percent": 1}


class TestPipelineSeam:
    def test_pipeline_applies_normalization_when_enabled(self) -> None:
        output = TextPipeline(max_text_chars=200, normalize=True).process("Pay 25% now.")
        assert output.text == "Pay 25 percent now."
        assert "normalize" in output.timings_ms

    def test_pipeline_pass_through_when_disabled(self) -> None:
        output = TextPipeline(max_text_chars=200, normalize=False).process("Pay 25% now.")
        assert output.text == "Pay 25% now."

    def test_validation_counts_original_characters_not_normalized(self) -> None:
        # "$9" expands to more characters than the input; the length law
        # applies to what the CUSTOMER sent, never to our expansion.
        text = "$9" * 10  # 20 chars input; expansion is ~9x longer
        output = TextPipeline(max_text_chars=20, normalize=True).process(text)
        assert len(output.text) > 20  # expanded internally, still accepted
