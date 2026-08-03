"""Speech-generation evaluation corpora — permanent, versioned, text-first.

**Corpora are permanent product assets of IntelliAI.** Models improve;
corpora accumulate. A corpus is not a test fixture — it is evaluation
capital, treated with the same permanence as datasets and benchmark
ledgers.

**Evolution rule (absolute):** a released corpus version never changes
once any recorded result cites it. New coverage always creates the next
version. Old benchmark results must remain reproducible forever — the
evaluation history survives indefinitely.

For generation, the input text IS the reference (nothing to record, no
hashes to pin), so a corpus is pure committed text: cases organized by
CATEGORY within language, because category-level scores localize
failures ("numbers regressed in Hindi") where one average hides them
(SPEECH_EVALUATION.md §5). Each case also declares DIFFICULTY
(orthogonal to category — general English has easy and hard sentences),
so reports can slice overall/easy/hard without corpus changes, and may
carry maintenance TAGS documenting why it exists (never scoring inputs).
Trap words drive `pronunciation_accuracy`: the words a case exists to
stress, validated at load time to actually appear in the text — a typo
in a trap is a build failure, not a silent scoring hole.
"""

from __future__ import annotations

import datetime
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


@unique
class Difficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@unique
class CaseTag(StrEnum):
    """Maintenance documentation, never scoring input. Append-only."""

    EXPECTED_FAILURE = "expected_failure"  # exposes a known current weakness
    KNOWN_LIMITATION = "known_limitation"  # tracks a stated platform limit
    REGRESSION_SENSITIVE = "regression_sensitive"  # historically fragile; watch


class CorpusProvenance(BaseModel):
    """Who made this corpus, when, and why — reproducible and auditable
    even when every sentence is written in-house."""

    model_config = ConfigDict(frozen=True)

    author: str = Field(min_length=1)
    created: datetime.date
    rationale: str = Field(min_length=1)
    source: str = Field(min_length=1)  # "original" | "adapted" | "synthetic"
    languages: tuple[str, ...] = Field(min_length=1)
    license: str | None = None  # only when material is not original


class SpeechTextCase(BaseModel):
    """One synthesis case: the text to speak and the words it stresses."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    language: str = Field(min_length=1)  # "en", "hi", "mixed"
    category: TextCategory
    difficulty: Difficulty
    text: str = Field(min_length=1)
    trap_words: tuple[str, ...] = ()  # scored strictly by pronunciation_accuracy
    tags: tuple[CaseTag, ...] = ()  # documentation, never scoring
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
    provenance: CorpusProvenance
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
