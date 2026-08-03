"""Speech corpus schema and the shipped tts-eval-v1 manifest."""

import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from intelliai_evaluation.corpus import (
    CaseTag,
    CorpusProvenance,
    Difficulty,
    SpeechCorpus,
    SpeechTextCase,
    TextCategory,
    load_corpus,
)

CORPUS_PATH = Path(__file__).resolve().parents[1] / "tts" / "corpora" / "tts-eval-v1.json"

PROVENANCE = CorpusProvenance(
    author="IntelliAI (in-house)",
    created=datetime.date(2026, 8, 3),
    rationale="test corpus",
    source="original",
    languages=("en",),
)


def case(**overrides: object) -> SpeechTextCase:
    fields: dict[str, object] = {
        "id": "en-test-01",
        "language": "en",
        "category": TextCategory.GENERAL,
        "difficulty": Difficulty.EASY,
        "text": "hello evaluation world",
        "trap_words": ("evaluation",),
    }
    fields.update(overrides)
    return SpeechTextCase.model_validate(fields)


def corpus_of(*cases: SpeechTextCase) -> SpeechCorpus:
    return SpeechCorpus(name="x", version=1, provenance=PROVENANCE, cases=cases)


class TestSchema:
    def test_trap_words_must_appear_in_text(self) -> None:
        with pytest.raises(ValidationError, match="does not appear"):
            case(trap_words=("missing",))

    def test_trap_matching_is_case_insensitive(self) -> None:
        assert case(text="The API gateway", trap_words=("api",)).trap_words == ("api",)

    def test_unknown_category_difficulty_or_tag_rejected(self) -> None:
        with pytest.raises(ValidationError):
            case(category="freestyle")
        with pytest.raises(ValidationError):
            case(difficulty="impossible")
        with pytest.raises(ValidationError):
            case(tags=("shiny",))

    def test_tags_are_documentation_vocabulary(self) -> None:
        tagged = case(tags=(CaseTag.EXPECTED_FAILURE, CaseTag.REGRESSION_SENSITIVE))
        assert CaseTag.EXPECTED_FAILURE in tagged.tags

    def test_duplicate_ids_rejected(self) -> None:
        with pytest.raises(ValidationError, match="unique"):
            corpus_of(case(), case())

    def test_empty_corpus_rejected(self) -> None:
        with pytest.raises(ValidationError, match="at least one"):
            corpus_of()

    def test_provenance_is_required_and_frozen(self) -> None:
        with pytest.raises(ValidationError):
            SpeechCorpus.model_validate({"name": "x", "version": 1, "cases": []})
        corpus = corpus_of(case())
        with pytest.raises(ValidationError):
            corpus.version = 2  # type: ignore[misc]


class TestShippedCorpus:
    """The real tts-eval-v1 manifest is validated by CI on every run."""

    def test_loads_and_validates(self) -> None:
        corpus = load_corpus(CORPUS_PATH)
        assert corpus.name == "tts-eval-seed"
        assert corpus.version == 1
        assert len(corpus.cases) >= 24

    def test_provenance_recorded(self) -> None:
        provenance = load_corpus(CORPUS_PATH).provenance
        assert provenance.source == "original"
        assert set(provenance.languages) == {"en", "hi", "mixed"}
        assert provenance.license is None  # in-house text

    def test_covers_all_three_language_groups(self) -> None:
        corpus = load_corpus(CORPUS_PATH)
        assert {c.language for c in corpus.cases} == {"en", "hi", "mixed"}

    def test_covers_every_planned_category(self) -> None:
        corpus = load_corpus(CORPUS_PATH)
        assert {c.category for c in corpus.cases} == set(TextCategory)

    def test_covers_every_difficulty(self) -> None:
        corpus = load_corpus(CORPUS_PATH)
        assert {c.difficulty for c in corpus.cases} == set(Difficulty)

    def test_hard_by_design_cases_are_tagged(self) -> None:
        corpus = load_corpus(CORPUS_PATH)
        for text_case in corpus.cases:
            if text_case.category in (TextCategory.URLS, TextCategory.EMAILS):
                assert CaseTag.EXPECTED_FAILURE in text_case.tags, text_case.id

    def test_category_grouping_is_total(self) -> None:
        corpus = load_corpus(CORPUS_PATH)
        grouped = corpus.by_category()
        assert sum(len(cases) for cases in grouped.values()) == len(corpus.cases)

    def test_hindi_cases_are_devanagari(self) -> None:
        corpus = load_corpus(CORPUS_PATH)
        for text_case in corpus.cases:
            if text_case.language == "hi":
                assert any("ऀ" <= ch <= "ॿ" for ch in text_case.text), text_case.id
