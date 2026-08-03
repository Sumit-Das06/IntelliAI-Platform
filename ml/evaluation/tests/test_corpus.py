"""Speech corpus schema and the shipped tts-eval-v1 manifest."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from intelliai_evaluation.corpus import (
    SpeechCorpus,
    SpeechTextCase,
    TextCategory,
    load_corpus,
)

CORPUS_PATH = Path(__file__).resolve().parents[1] / "tts" / "corpora" / "tts-eval-v1.json"


def case(**overrides: object) -> SpeechTextCase:
    fields: dict[str, object] = {
        "id": "en-test-01",
        "language": "en",
        "category": TextCategory.GENERAL,
        "text": "hello evaluation world",
        "trap_words": ("evaluation",),
    }
    fields.update(overrides)
    return SpeechTextCase.model_validate(fields)


class TestSchema:
    def test_trap_words_must_appear_in_text(self) -> None:
        with pytest.raises(ValidationError, match="does not appear"):
            case(trap_words=("missing",))

    def test_trap_matching_is_case_insensitive(self) -> None:
        assert case(text="The API gateway", trap_words=("api",)).trap_words == ("api",)

    def test_unknown_category_rejected(self) -> None:
        with pytest.raises(ValidationError):
            case(category="freestyle")

    def test_duplicate_ids_rejected(self) -> None:
        with pytest.raises(ValidationError, match="unique"):
            SpeechCorpus(name="x", version=1, cases=(case(), case()))

    def test_empty_corpus_rejected(self) -> None:
        with pytest.raises(ValidationError, match="at least one"):
            SpeechCorpus(name="x", version=1, cases=())

    def test_frozen(self) -> None:
        corpus = SpeechCorpus(name="x", version=1, cases=(case(),))
        with pytest.raises(ValidationError):
            corpus.version = 2  # type: ignore[misc]


class TestShippedCorpus:
    """The real tts-eval-v1 manifest is validated by CI on every run."""

    def test_loads_and_validates(self) -> None:
        corpus = load_corpus(CORPUS_PATH)
        assert corpus.name == "tts-eval-seed"
        assert corpus.version == 1
        assert len(corpus.cases) >= 24

    def test_covers_all_three_language_groups(self) -> None:
        corpus = load_corpus(CORPUS_PATH)
        assert {case.language for case in corpus.cases} == {"en", "hi", "mixed"}

    def test_covers_every_planned_category(self) -> None:
        corpus = load_corpus(CORPUS_PATH)
        covered = {case.category for case in corpus.cases}
        assert covered == set(TextCategory)  # v1 exercises the full vocabulary

    def test_category_grouping_is_total(self) -> None:
        corpus = load_corpus(CORPUS_PATH)
        grouped = corpus.by_category()
        assert sum(len(cases) for cases in grouped.values()) == len(corpus.cases)

    def test_hindi_cases_are_devanagari(self) -> None:
        corpus = load_corpus(CORPUS_PATH)
        for text_case in corpus.cases:
            if text_case.language == "hi":
                assert any("ऀ" <= ch <= "ॿ" for ch in text_case.text), text_case.id
