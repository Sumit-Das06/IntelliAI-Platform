"""M39 Hindi normalization v1 — deterministic rule-pack laws.

Mirror of the M35 English suite: every rule proven on the exact forms
the M38 benchmark measured, idempotency, pass-through for everything
out of scope, and the no-English-words law (a Hindi normalization that
emits "rupees" would be the M38 production-path defect reborn).
"""

import pytest

from intelliai_tts_runtime.normalization_hi import normalize_for_speech_hindi


def norm(text: str) -> str:
    return normalize_for_speech_hindi(text).text


class TestRupees:
    def test_symbol_and_grouping_commas(self) -> None:
        assert norm("इसकी कीमत ₹12,500 है।") == "इसकी कीमत 12500 रुपये है।"

    def test_paise(self) -> None:
        assert norm("कुल ₹1,499.50 है।") == "कुल 1499 रुपये और 50 पैसे है।"

    def test_one_rupee_singular(self) -> None:
        assert norm("₹1 का सिक्का") == "1 रुपया का सिक्का"

    def test_rule_hit_recorded(self) -> None:
        assert normalize_for_speech_hindi("₹99 दें").rule_hits == {"rupees": 1}


class TestDates:
    def test_slash_date_expands_to_hindi_month(self) -> None:
        assert norm("आपकी नियुक्ति 12/08/2026 को है।") == "आपकी नियुक्ति 12 अगस्त 2026 को है।"

    def test_swapped_month_day_still_reads(self) -> None:
        assert norm("8/13/2026") == "13 अगस्त 2026"

    def test_unparseable_passes_through(self) -> None:
        assert norm("99/99/2026") == "99/99/2026"

    def test_plain_written_date_untouched(self) -> None:
        assert norm("12 अगस्त 2026 को बैठक होगी।") == "12 अगस्त 2026 को बैठक होगी।"


class TestPercent:
    def test_percent_sign(self) -> None:
        assert norm("कृपया मुझे 25% छूट दें।") == "कृपया मुझे 25 प्रतिशत छूट दें।"

    def test_decimal_percent(self) -> None:
        assert norm("ब्याज 2.5% है") == "ब्याज 2.5 प्रतिशत है"


class TestDevanagariDigits:
    def test_digits_become_ascii(self) -> None:
        assert norm("कक्षा में ४५ विद्यार्थी हैं।") == "कक्षा में 45 विद्यार्थी हैं।"

    def test_rule_hit_recorded(self) -> None:
        assert normalize_for_speech_hindi("९ बजे").rule_hits == {"devanagari_digits": 1}


class TestTime:
    def test_am_time(self) -> None:
        assert norm("डिलीवरी 10:30 AM तक पहुँचेगी।") == "डिलीवरी सुबह 10 बजकर 30 मिनट तक पहुँचेगी।"

    def test_pm_time_on_the_hour(self) -> None:
        assert norm("बैठक 5:00 PM पर है") == "बैठक शाम 5 बजे पर है"

    def test_bare_clock_time_is_out_of_scope_v1(self) -> None:
        assert norm("सुबह 10:30 पर") == "सुबह 10:30 पर"


class TestPhone:
    def test_ten_digit_mobile_spoken_digit_by_digit(self) -> None:
        assert norm("मेरा नंबर 9876543210 है।") == ("मेरा नंबर नौ आठ सात छह पाँच, चार तीन दो एक शून्य है।")

    def test_grouped_helpline(self) -> None:
        assert norm("हेल्पलाइन 1800 425 9090 पर कॉल करें।") == (
            "हेल्पलाइन एक आठ शून्य शून्य, चार दो पाँच, नौ शून्य नौ शून्य पर कॉल करें।"
        )

    def test_plus_country_code(self) -> None:
        assert norm("+91 98765 43210") == ("प्लस नौ एक, नौ आठ सात छह पाँच, चार तीन दो एक शून्य")

    def test_short_ids_stay_numbers(self) -> None:
        # 5-digit policy/train numbers keep espeak's Hindi number reading.
        assert norm("मेरा policy number 12345 है।") == "मेरा policy number 12345 है।"
        assert norm("ट्रेन संख्या 12951 सुबह छूटती है।") == "ट्रेन संख्या 12951 सुबह छूटती है।"


class TestLaws:
    CASES = (
        "इसकी कीमत ₹12,500 है।",
        "आपकी नियुक्ति 12/08/2026 को है।",
        "कृपया मुझे 25% छूट दें।",
        "मेरा नंबर 9876543210 है।",
        "कक्षा में ४५ विद्यार्थी हैं।",
        "डिलीवरी 10:30 AM तक पहुँचेगी।",
        "हेल्पलाइन 1800 425 9090 पर कॉल करें।",
    )

    @pytest.mark.parametrize("text", CASES)
    def test_idempotent(self, text: str) -> None:
        once = norm(text)
        assert norm(once) == once

    @pytest.mark.parametrize("text", CASES)
    def test_no_english_words_ever(self, text: str) -> None:
        result = norm(text)
        for english in ("rupees", "percent", "August", "zero", "one", "two"):
            assert english not in result

    def test_ordinary_hindi_passes_through_byte_identical(self) -> None:
        text = "नमस्ते, आप कैसे हैं? मुझे आज का मौसम बहुत अच्छा लगा।"
        result = normalize_for_speech_hindi(text)
        assert result.text == text
        assert result.rule_hits == {}

    def test_devanagari_digits_feed_later_rules(self) -> None:
        # Devanagari digits normalize FIRST, so a Devanagari-digit
        # percent still expands.
        assert norm("२५% छूट") == "25 प्रतिशत छूट"
