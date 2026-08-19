"""Punctuation scoring: the slot ruler, the safety invariant, the policies.

The laws held here: extraction is deterministic and symmetric (unscored
punctuation can never flip a verdict); the invariant is a gate, not a
metric; "." and "।" stay distinct per-mark but share the sentence-boundary
group; the shipped hi-punct-eval@v1 manifest is valid and pinned.
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from intelliai_evaluation.punctuation import (
    PUNCTUATION_RULER,
    SENTENCE_END_MARKS,
    SUPPORTED_MARKS,
    Counts,
    PunctuationDataset,
    depunct,
    extract,
    invariant_holds,
    load_punctuation_dataset,
    score_corpus,
    score_pair,
    strip_punctuation_for_input,
)

MANIFEST = Path("ml/evaluation/punctuation/datasets/hi-punct-eval-v1.json")

DANDA = "।"
ZWJ = "‍"  # zero-width joiner (category Cf)


class TestExtraction:
    def test_danda_lands_in_the_slot_after_its_word(self) -> None:
        got = extract(f"मैं घर जा रहा हूँ{DANDA} आप कौन हैं?")
        assert got.words == ("मैं", "घर", "जा", "रहा", "हूँ", "आप", "कौन", "हैं")
        assert got.slots[5] == (DANDA,)
        assert got.slots[8] == ("?",)

    def test_a_standalone_mark_token_attaches_to_the_preceding_word(self) -> None:
        assert extract(f"ठीक है {DANDA}").slots[2] == (DANDA,)

    def test_slot_zero_catches_marks_before_any_word(self) -> None:
        got = extract(f"{DANDA} शुरू")
        assert got.slots[0] == (DANDA,)
        assert got.words == ("शुरू",)

    def test_unsupported_marks_are_ignored_symmetrically(self) -> None:
        # Parens, quotes, hyphens: not scored, and they still separate words
        # exactly like depunct does.
        got = extract('उन्होंने ("हाई-किंग") कहा')
        assert got.words == ("उन्होंने", "हाई", "किंग", "कहा")
        assert all(slot == () for slot in got.slots)

    def test_url_dots_split_words_the_same_way_on_both_sides(self) -> None:
        got = extract("साइट intelliai.example.com पर जाएँ")
        assert got.words == ("साइट", "intelliai", "example", "com", "पर", "जाएँ")
        assert got.slots[2] == (".",)
        assert got.slots[3] == (".",)

    def test_words_are_casefolded_and_nfc(self) -> None:
        assert extract("Hello WORLD").words == ("hello", "world")

    def test_format_characters_are_deleted_not_spaced(self) -> None:
        # The unicode_generic@v2 lesson: ZWJ must not split a conjunct.
        assert extract(f"क{ZWJ}ख").words == (f"क{ZWJ}ख".replace(ZWJ, ""),)

    def test_extraction_matches_depunct_word_for_word(self) -> None:
        text = f"एकदम ठीक{DANDA} क्या आप, आ रहे हैं? हाँ!"
        assert " ".join(extract(text).words) == depunct(text)


class TestInvariant:
    def test_adding_punctuation_passes(self) -> None:
        assert invariant_holds("मैं घर जा रहा हूँ", f"मैं घर जा रहा हूँ{DANDA}")

    def test_changing_a_word_fails(self) -> None:
        assert not invariant_holds("आप कहाँ जा रहे हैं", "आप कहाँ जा रहे हो?")

    def test_dropping_a_word_fails(self) -> None:
        assert not invariant_holds("मैं अपने घर जा रहा हूँ", f"मैं घर जा रहा हूँ{DANDA}")

    def test_case_and_whitespace_do_not_fail_it(self) -> None:
        assert invariant_holds("hello   world", "Hello, world.")


class TestScoring:
    def test_perfect_restoration_scores_one(self) -> None:
        reference = f"खाना तैयार है{DANDA} सब आ जाओ{DANDA}"
        pair = score_pair(reference, reference)
        assert pair.aligned
        assert pair.micro.f1 == 1.0
        assert pair.per_mark[DANDA].true_positives == 2

    def test_noop_scores_zero_with_full_recall_deficit(self) -> None:
        reference = f"खाना तैयार है{DANDA} सब आ जाओ{DANDA}"
        pair = score_pair(reference, strip_punctuation_for_input(reference))
        assert pair.aligned
        assert pair.micro.f1 == 0.0
        assert pair.micro.false_negatives == 2
        assert pair.micro.false_positives == 0

    def test_a_wrong_position_costs_both_precision_and_recall(self) -> None:
        reference = f"ठीक है{DANDA} चलो"
        predicted = f"ठीक है चलो{DANDA}"
        pair = score_pair(reference, predicted)
        assert pair.micro.true_positives == 0
        assert pair.micro.false_positives == 1
        assert pair.micro.false_negatives == 1

    def test_full_stop_and_danda_differ_per_mark_but_share_the_boundary(self) -> None:
        # The documented FLEURS policy: per-mark keeps them distinct;
        # sentence-boundary scoring treats either as the same event.
        reference = f"स्की मार्ग को सोचें{DANDA}"
        predicted = "स्की मार्ग को सोचें."
        pair = score_pair(reference, predicted)
        assert pair.per_mark[DANDA].false_negatives == 1
        assert pair.per_mark["."].false_positives == 1
        assert pair.boundary.true_positives == 1
        assert pair.boundary.f1 == 1.0

    def test_an_unaligned_pair_is_refused_not_scored(self) -> None:
        pair = score_pair(f"मैं घर जा रहा हूँ{DANDA}", f"मैं अपने घर जा रहा हूँ{DANDA}")
        assert not pair.aligned
        assert pair.micro.true_positives == 0

    def test_multiset_slots_count_duplicates_honestly(self) -> None:
        reference = "अरे!! रुको"
        predicted = "अरे! रुको"
        pair = score_pair(reference, predicted)
        assert pair.per_mark["!"].true_positives == 1
        assert pair.per_mark["!"].false_negatives == 1

    def test_degenerate_zero_conventions(self) -> None:
        counts = Counts()
        assert counts.precision == 0.0
        assert counts.recall == 0.0
        assert counts.f1 == 0.0

    def test_corpus_aggregation_counts_unsafe_rows_without_scoring_them(self) -> None:
        reference = f"ठीक है{DANDA}"
        corpus = score_corpus(
            [
                (reference, reference),  # perfect
                (reference, "बिल्कुल ठीक है।"),  # word added -> unsafe
            ]
        )
        assert corpus.rows == 2
        assert corpus.aligned_rows == 1
        assert corpus.invariant_failures == 1
        assert corpus.invariant_pass_rate == 0.5
        assert corpus.micro.f1 == 1.0  # only the safe row is counted

    def test_scoring_is_deterministic(self) -> None:
        reference = f"क्या आप आओगे? हाँ{DANDA}"
        predicted = f"क्या आप आओगे{DANDA} हाँ?"
        first = score_pair(reference, predicted).micro.as_dict()
        second = score_pair(reference, predicted).micro.as_dict()
        assert first == second


class TestInputPreparation:
    def test_strip_preserves_case_and_removes_all_punctuation(self) -> None:
        got = strip_punctuation_for_input(f"Dr. शर्मा आएँगे{DANDA} (कल)")
        assert got == "Dr शर्मा आएँगे कल"

    def test_strip_deletes_format_characters(self) -> None:
        assert strip_punctuation_for_input(f"क{ZWJ}ख") == "कख"


class TestShippedManifest:
    def test_the_v1_manifest_is_valid_and_pinned(self) -> None:
        dataset = load_punctuation_dataset(MANIFEST)
        assert dataset.name == "hi-punct-eval"
        assert dataset.version == 1
        assert dataset.task == "punctuation-restoration"
        assert len(dataset.rows) == 265  # 418 FLEURS hi_in test rows, deduped
        assert all(row.language == "hi" for row in dataset.rows)

    def test_almost_every_reference_carries_punctuation(self) -> None:
        dataset = load_punctuation_dataset(MANIFEST)
        with_marks = sum(
            1 for row in dataset.rows if any(mark in row.reference_text for mark in SUPPORTED_MARKS)
        )
        # The source measured 99.8% punctuated; dedup keeps that property.
        assert with_marks >= len(dataset.rows) - 2

    def test_every_row_keeps_its_source_audio_identity(self) -> None:
        dataset = load_punctuation_dataset(MANIFEST)
        for row in dataset.rows:
            assert row.source.files
            assert len(row.source.files) == len(row.source.duration_seconds)

    def test_the_schema_refuses_duplicate_ids(self) -> None:
        payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
        payload["rows"] = [payload["rows"][0], payload["rows"][0]]
        with pytest.raises(ValidationError):
            PunctuationDataset.model_validate(payload)

    def test_the_schema_refuses_an_unnormalized_reference(self) -> None:
        payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
        payload["rows"][0]["reference_text"] = "double  space"
        with pytest.raises(ValidationError):
            PunctuationDataset.model_validate(payload)


class TestRulerIdentity:
    def test_the_ruler_name_and_mark_sets_are_pinned(self) -> None:
        assert PUNCTUATION_RULER == "punct_slots@v1"
        assert SUPPORTED_MARKS == (DANDA, ",", "?", "!", ".")
        assert {DANDA, "?", "!", "."} == SENTENCE_END_MARKS
