"""Round-trip correctness metrics: the platform's ears grade its mouth.

`round_trip_wer` and `pronunciation_accuracy` score a judge transcript
against the INPUT TEXT of a synthesis case. Both are pure functions of
two strings (plus trap words) — no engine, no capability, no network:
the runner (D5) supplies the transcript however it likes.

Normalization here is `speech_normalize` — Unicode-aware (Devanagari
matras and conjuncts survive; the STT seed's English-oriented
`normalize_words` would erase them). It is a DIFFERENT normalization and
therefore a DIFFERENT metric family from the STT WER: same frozen
alignment core (`wer.align_words`), separate ruler, per the
a-changed-metric-is-a-new-metric law.
"""

from __future__ import annotations

import unicodedata

from intelliai_evaluation.wer import WerBreakdown, align_words

# Unicode categories kept as word content: Letters, Marks (matras and
# combining signs), Numbers. Everything else separates words. Apostrophes
# survive inside contractions, mirroring the STT ruler's choice.
_KEEP = ("L", "M", "N")


def speech_normalize(text: str) -> list[str]:
    """Text -> comparable tokens, for any script.

    casefold -> NFC (one canonical byte form per Devanagari cluster) ->
    keep letters/marks/numbers/apostrophes, everything else becomes a
    space -> split -> strip edge apostrophes."""
    composed = unicodedata.normalize("NFC", text.casefold())
    kept = "".join(
        ch if unicodedata.category(ch)[0] in _KEEP or ch == "'" else " " for ch in composed
    )
    return [stripped for word in kept.split() if (stripped := word.strip("'"))]


def round_trip_wer(input_text: str, transcript: str) -> WerBreakdown:
    """WER of the judge's transcript against the synthesis input text."""
    return align_words(speech_normalize(input_text), speech_normalize(transcript))


def pronunciation_accuracy(trap_words: tuple[str, ...], transcript: str) -> float | None:
    """Fraction of trap words surviving the round trip; None when a case
    declares no traps (absence of traps is not a perfect score).

    A trap hits when its normalized token sequence appears contiguously
    in the normalized transcript — multi-token traps ("careers example
    com") must survive whole, not as scattered fragments."""
    if not trap_words:
        return None
    transcript_tokens = speech_normalize(transcript)
    hits = 0
    for trap in trap_words:
        trap_tokens = speech_normalize(trap)
        if trap_tokens and _contains_sequence(transcript_tokens, trap_tokens):
            hits += 1
    return hits / len(trap_words)


def _contains_sequence(haystack: list[str], needle: list[str]) -> bool:
    if len(needle) > len(haystack):
        return False
    return any(
        haystack[start : start + len(needle)] == needle
        for start in range(len(haystack) - len(needle) + 1)
    )
