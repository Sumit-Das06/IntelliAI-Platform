"""Speech-generation evaluation corpora — versioned, immutable, text-first.

For generation, the input text IS the reference (nothing to record, no
hashes to pin), so a corpus is pure committed text: cases organized by
CATEGORY within language, because category-level scores localize
failures ("numbers regressed in Hindi") where one average hides them
(SPEECH_EVALUATION.md §5). Released corpora are immutable; new text is
the next version. Trap words drive `pronunciation_accuracy`: the words a
case exists to stress, validated at load time to actually appear in the
text — a typo in a trap is a build failure, not a silent scoring hole.
"""

from __future__ import annotations

import json
from enum import StrEnum, unique
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator


@unique
class TextCategory(StrEnum):
    """Corpus categories — append-only vocabulary, like every platform enum.

    A category names a failure mode worth isolating; future capabilities
    (robustness families, new languages) append members, never rename."""

    GENERAL = "general"
    NUMBERS = "numbers"
    DATES = "dates"
    CURRENCY = "currency"
    URLS = "urls"
    EMAILS = "emails"
    TECHNICAL = "technical"
    CONJUNCTS = "conjuncts"
    MATRAS = "matras"
    PROPER_NAMES = "proper_names"
    CODE_MIXED = "code_mixed"
    API_TERMS = "api_terms"
    PROGRAMMING = "programming"


class SpeechTextCase(BaseModel):
    """One synthesis case: the text to speak and the words it stresses."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    language: str = Field(min_length=1)  # "en", "hi", "mixed"
    category: TextCategory
    text: str = Field(min_length=1)
    trap_words: tuple[str, ...] = ()  # scored strictly by pronunciation_accuracy
    notes: str = ""

    @model_validator(mode="after")
    def _traps_appear_in_text(self) -> SpeechTextCase:
        lowered = self.text.casefold()
        for trap in self.trap_words:
            if trap.casefold() not in lowered:
                msg = f"case {self.id!r}: trap word {trap!r} does not appear in the text"
                raise ValueError(msg)
        return self


class SpeechCorpus(BaseModel):
    """A versioned, immutable set of synthesis cases."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    version: int = Field(ge=1)
    description: str = ""
    cases: tuple[SpeechTextCase, ...]

    @model_validator(mode="after")
    def _unique_ids(self) -> SpeechCorpus:
        ids = [case.id for case in self.cases]
        if len(ids) != len(set(ids)):
            msg = f"corpus {self.name!r}: case ids must be unique"
            raise ValueError(msg)
        if not self.cases:
            msg = f"corpus {self.name!r}: at least one case is required"
            raise ValueError(msg)
        return self

    def by_category(self) -> dict[TextCategory, tuple[SpeechTextCase, ...]]:
        """Category-level grouping — the unit of score reporting."""
        grouped: dict[TextCategory, list[SpeechTextCase]] = {}
        for case in self.cases:
            grouped.setdefault(case.category, []).append(case)
        return {category: tuple(cases) for category, cases in grouped.items()}


def load_corpus(path: Path) -> SpeechCorpus:
    """Load and validate a corpus manifest from JSON."""
    return SpeechCorpus.model_validate(json.loads(path.read_text(encoding="utf-8")))
