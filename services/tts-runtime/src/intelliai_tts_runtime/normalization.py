"""Text normalization v1 — deterministic, rule-scoped, speech-only (M35).

The pipeline's reserved seam, finally occupied. Scope is deliberately
narrow: written forms that the M32/M33/M34 benchmarks MEASURED being
mispronounced — currency, percentages, slash-dates, phone-style digit
groups. Nothing else changes: names, ordinary words, plain numbers, and
everything the engine already says correctly pass through byte-identical.

Laws:
- **Speech-only.** The normalized string exists for the engine; the
  request text remains the billing and provenance fact (routes.py counts
  characters on the ORIGINAL text; the gateway never sees this form).
- **Deterministic and idempotent.** Same input, same output, forever;
  running the normalizer on its own output changes nothing (expansions
  produce plain words that no rule matches again).
- **No general grammar.** A form outside these rules is not our business
  in v1 — it passes through untouched.

Every rule is documented at its pattern. Currency symbols are expanded
because the engines drop or misread them (₹ dropped, "$4.99" read as
"dollar four point nine nine"); digit GROUPS in phone-like sequences are
spelled digit-by-digit because that is how humans read them aloud.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

_DIGIT_WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine")

#: DD/MM/YYYY (Indian convention, documented) -> "12 August 2026".
#: Month > 12 with day <= 12 is treated as MM/DD swapped input and still
#: rendered from the valid reading; anything unparseable passes through.
_SLASH_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")

#: Currency amounts. "$4.99" -> "4 dollars and 99 cents"; "$5" ->
#: "5 dollars"; "₹12,500" -> "12500 rupees" (Indian digit-grouping commas
#: removed so the engine reads one number). "Rs." style is out of scope v1.
_DOLLARS = re.compile(r"\$\s?(\d+(?:,\d{2,3})*)(?:\.(\d{1,2}))?\b")
_RUPEES = re.compile(r"₹\s?(\d+(?:,\d{2,3})*)(?:\.(\d{1,2}))?\b")

#: Percentages: "25%" -> "25 percent", "2.5%" -> "2.5 percent".
_PERCENT = re.compile(r"\b(\d+(?:\.\d+)?)\s?%")

#: Phone-style digit groups: an optional +CC prefix and/or 2+ groups of
#: 3-5 digits separated by spaces/hyphens ("+91 98765 43210",
#: "1800 425 9090") -> each digit spoken ("nine one, nine eight ...").
#: Single numbers ("1247", years, "August 3, 2026") never match: the
#: pattern requires a leading + or at least two groups.
_PHONE = re.compile(r"(?<![\d.,])(\+\d{1,3}[ -]?)?(\d{3,5}(?:[ -]\d{3,5}){1,4})(?![\d.,])")


@dataclass(frozen=True)
class NormalizationResult:
    text: str
    rule_hits: dict[str, int]


def _spell_digits(digits: str) -> str:
    return " ".join(_DIGIT_WORDS[int(ch)] for ch in digits if ch.isdigit())


def _expand_slash_date(match: re.Match[str]) -> str:
    first, second, year = int(match.group(1)), int(match.group(2)), match.group(3)
    day, month = first, second
    if month > 12 and day <= 12:
        day, month = second, first
    if not (1 <= day <= 31 and 1 <= month <= 12):
        return match.group(0)
    return f"{day} {_MONTHS[month - 1]} {year}"


def _expand_dollars(match: re.Match[str]) -> str:
    whole = match.group(1).replace(",", "")
    cents = match.group(2)
    unit = "dollar" if whole == "1" else "dollars"
    if cents and int(cents) > 0:
        cents_normalized = int(cents if len(cents) == 2 else cents + "0")
        cent_unit = "cent" if cents_normalized == 1 else "cents"
        return f"{whole} {unit} and {cents_normalized} {cent_unit}"
    return f"{whole} {unit}"


def _expand_rupees(match: re.Match[str]) -> str:
    whole = match.group(1).replace(",", "")
    paise = match.group(2)
    unit = "rupee" if whole == "1" else "rupees"
    if paise and int(paise) > 0:
        return f"{whole} {unit} and {int(paise)} paise"
    return f"{whole} {unit}"


def _expand_phone(match: re.Match[str]) -> str:
    prefix, groups = match.group(1), match.group(2)
    spoken: list[str] = []
    if prefix:
        spoken.append("plus " + _spell_digits(prefix))
    spoken.extend(_spell_digits(group) for group in re.split(r"[ -]", groups))
    return ", ".join(part for part in spoken if part)


def normalize_for_speech(text: str) -> NormalizationResult:
    """Apply the v1 rules in a fixed order; count what fired.

    Order matters and is fixed: dates before phone (so a slash-date is
    never mistaken for digit groups), currency before phone (so amounts
    keep their number reading), percent independent of both.
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

    normalized = _run("slash_date", _SLASH_DATE, _expand_slash_date, text)
    normalized = _run("dollars", _DOLLARS, _expand_dollars, normalized)
    normalized = _run("rupees", _RUPEES, _expand_rupees, normalized)
    normalized = _run("percent", _PERCENT, r"\1 percent", normalized)
    normalized = _run("phone", _PHONE, _expand_phone, normalized)
    return NormalizationResult(text=normalized, rule_hits=hits)
