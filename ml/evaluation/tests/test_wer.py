"""The metric must be beyond suspicion: known alignments, exact counts."""

import pytest

from intelliai_evaluation.wer import normalize_words, word_error_rate


class TestNormalization:
    def test_case_and_punctuation_are_ignored(self) -> None:
        assert normalize_words("Hello, World!") == ["hello", "world"]

    def test_contractions_survive(self) -> None:
        assert normalize_words("don't stop") == ["don't", "stop"]

    def test_edge_apostrophes_are_stripped(self) -> None:
        assert normalize_words("'quoted' words") == ["quoted", "words"]

    def test_empty_and_whitespace(self) -> None:
        assert normalize_words("") == []
        assert normalize_words("   \n\t ") == []


class TestWordErrorRate:
    def test_identical_texts_have_zero_errors(self) -> None:
        result = word_error_rate("the quick brown fox", "the quick brown fox")
        assert result.errors == 0
        assert result.wer == 0.0

    def test_identical_up_to_normalization(self) -> None:
        reference = "And so, my fellow Americans: ask not!"
        hypothesis = "and so my fellow americans ask not"
        assert word_error_rate(reference, hypothesis).errors == 0

    def test_single_substitution(self) -> None:
        result = word_error_rate("the quick brown fox", "the quick brown dog")
        assert (result.substitutions, result.insertions, result.deletions) == (1, 0, 0)
        assert result.wer == pytest.approx(0.25)

    def test_single_deletion(self) -> None:
        result = word_error_rate("the quick brown fox", "the quick fox")
        assert (result.substitutions, result.insertions, result.deletions) == (0, 0, 1)

    def test_single_insertion(self) -> None:
        result = word_error_rate("the quick fox", "the very quick fox")
        assert (result.substitutions, result.insertions, result.deletions) == (0, 1, 0)

    def test_mixed_operations(self) -> None:
        # ref: a b c d   hyp: a x c   → 1 substitution (b→x) + 1 deletion (d)
        result = word_error_rate("a b c d", "a x c")
        assert result.errors == 2
        assert result.wer == pytest.approx(0.5)

    def test_everything_wrong(self) -> None:
        result = word_error_rate("alpha beta", "gamma delta")
        assert result.substitutions == 2
        assert result.wer == pytest.approx(1.0)

    def test_wer_can_exceed_one(self) -> None:
        result = word_error_rate("hi", "well hello there friend")
        assert result.wer > 1.0

    def test_counts_are_exact(self) -> None:
        result = word_error_rate("one two three", "one two three four five")
        assert result.reference_words == 3
        assert result.hypothesis_words == 5
        assert result.insertions == 2

    def test_empty_reference_wer_is_undefined(self) -> None:
        result = word_error_rate("", "hallucinated words here")
        assert result.hypothesis_words == 3
        with pytest.raises(ValueError, match="empty reference"):
            _ = result.wer

    def test_deterministic_across_runs(self) -> None:
        first = word_error_rate("a b c d e", "b c x e")
        second = word_error_rate("a b c d e", "b c x e")
        assert first == second
