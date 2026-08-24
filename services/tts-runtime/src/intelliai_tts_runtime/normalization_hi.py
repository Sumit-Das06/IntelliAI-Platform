"""Hindi text normalization v1 — deterministic, rule-scoped, speech-only (M39).

The Hindi rule pack for the M35 pipeline seam. NOT a translation of the
English rules: espeak-ng's Hindi voice already reads bare digit strings
as Hindi number words (M38 measured: "12500" -> "बारह हज़ार पाँच सौ"), so
these rules only rewrite the WRITTEN FORMS the M32/M38 benchmarks
measured being dropped or misread — currency symbols, grouping commas,
slash-dates, percent signs, AM/PM times, Devanagari digits, and
phone-style digit runs. Digits stay digits wherever the engine already
says them correctly; no number words — Hindi or English — are ever
hard-coded for plain amounts.

Laws (same as the English pack):
- **Speech-only.** The original request text remains the billing and
  provenance fact; only the engine sees this form.
- **Deterministic and idempotent.** Same input, same output, forever;
  every expansion produces text no rule matches again.
- **No general grammar.** Anything outside these rules passes through.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from intelliai_tts_runtime.normalization import NormalizationResult

_HINDI_MONTHS = (
    "जनवरी",
    "फ़रवरी",
    "मार्च",
    "अप्रैल",
    "मई",
    "जून",
    "जुलाई",
    "अगस्त",
    "सितंबर",
    "अक्टूबर",
    "नवंबर",
    "दिसंबर",
)

_HINDI_DIGIT_WORDS = ("शून्य", "एक", "दो", "तीन", "चार", "पाँच", "छह", "सात", "आठ", "नौ")

#: Devanagari digits mapped to ASCII, so every later rule (and espeak's
#: own number reading) sees one digit alphabet. M38 measured a candidate
#: hard-crashing on Devanagari digits; ours must treat them as numbers.
_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")

#: DD/MM/YYYY (Indian convention) -> "12 अगस्त 2026". Month > 12 with
#: day <= 12 is treated as swapped input; unparseable passes through.
_SLASH_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")

#: "₹12,500" -> "12500 रुपये"; "₹1,499.50" -> "1499 रुपये और 50 पैसे".
#: Grouping commas removed so the engine reads ONE number (the measured
#: M32 defect: the comma broke espeak's number parsing; ₹ was dropped).
_RUPEES = re.compile(r"₹\s?(\d+(?:,\d{2,3})*)(?:\.(\d{1,2}))?\b")

#: "25%" -> "25 प्रतिशत" (espeak reads the digits in Hindi).
_PERCENT = re.compile(r"\b(\d+(?:\.\d+)?)\s?%")

#: "10:30 AM" -> "सुबह 10 बजकर 30 मिनट". Only with an explicit AM/PM
#: marker — a bare "10:30" stays untouched in v1 (deliberate scope).
_AMPM_TIME = re.compile(r"\b(\d{1,2}):(\d{2})\s?(AM|PM|am|pm)\b")

#: Phone-style digit sequences, spoken digit-by-digit in Hindi:
#: an optional +CC prefix and/or 2+ groups of 3-5 digits, OR one bare
#: 10-digit run (the Indian mobile shape M38 probes carry). Grouping
#: bounds mirror the English pack; years and small IDs never match.
_PHONE_GROUPED = re.compile(r"(?<![\d.,])(\+\d{1,3}[ -]?)?(\d{3,5}(?:[ -]\d{3,5}){1,4})(?![\d.,])")
_PHONE_TEN = re.compile(r"(?<![\d.,])(\d{10})(?![\d.,])")


def _spell_digits_hindi(digits: str) -> str:
    return " ".join(_HINDI_DIGIT_WORDS[int(ch)] for ch in digits if ch.isdigit())


def _expand_slash_date(match: re.Match[str]) -> str:
    first, second, year = int(match.group(1)), int(match.group(2)), match.group(3)
    day, month = first, second
    if month > 12 and day <= 12:
        day, month = second, first
    if not (1 <= day <= 31 and 1 <= month <= 12):
        return match.group(0)
    return f"{day} {_HINDI_MONTHS[month - 1]} {year}"


def _expand_rupees(match: re.Match[str]) -> str:
    whole = match.group(1).replace(",", "")
    paise = match.group(2)
    unit = "रुपया" if whole == "1" else "रुपये"
    if paise and int(paise) > 0:
        return f"{whole} {unit} और {int(paise)} पैसे"
    return f"{whole} {unit}"


def _expand_ampm(match: re.Match[str]) -> str:
    hour, minute, marker = match.group(1), int(match.group(2)), match.group(3).lower()
    daypart = "सुबह" if marker == "am" else "शाम"
    if minute == 0:
        return f"{daypart} {hour} बजे"
    return f"{daypart} {hour} बजकर {minute} मिनट"


def _expand_phone_grouped(match: re.Match[str]) -> str:
    prefix, groups = match.group(1), match.group(2)
    spoken: list[str] = []
    if prefix:
        spoken.append("प्लस " + _spell_digits_hindi(prefix))
    spoken.extend(_spell_digits_hindi(group) for group in re.split(r"[ -]", groups))
    return ", ".join(part for part in spoken if part)


def _expand_phone_ten(match: re.Match[str]) -> str:
    digits = match.group(1)
    return _spell_digits_hindi(digits[:5]) + ", " + _spell_digits_hindi(digits[5:])


def normalize_for_speech_hindi(text: str) -> NormalizationResult:
    """Apply the Hindi v1 rules in a fixed order; count what fired.

    Order is law: Devanagari digits first (every later rule sees ASCII),
    dates before phones (a slash-date is never digit groups), currency
    before phones (amounts keep their number reading), the 10-digit
    mobile rule after the grouped rule (a grouped match consumes its
    digits first).
    """
    hits: dict[str, int] = {}

    def _run(
        name: str,
        pattern: re.Pattern[str],
        repl: str | Callable[[re.Match[str]], str],
        value: str,
    ) -> str:
        result, count = pattern.subn(repl, value)
        if count:
            hits[name] = hits.get(name, 0) + count
        return result

    normalized = text.translate(_DEVANAGARI_DIGITS)
    if normalized != text:
        hits["devanagari_digits"] = 1
    normalized = _run("slash_date", _SLASH_DATE, _expand_slash_date, normalized)
    normalized = _run("rupees", _RUPEES, _expand_rupees, normalized)
    normalized = _run("percent", _PERCENT, r"\1 प्रतिशत", normalized)
    normalized = _run("time_ampm", _AMPM_TIME, _expand_ampm, normalized)
    normalized = _run("phone", _PHONE_GROUPED, _expand_phone_grouped, normalized)
    normalized = _run("phone_ten_digit", _PHONE_TEN, _expand_phone_ten, normalized)
    return NormalizationResult(text=normalized, rule_hits=hits)
