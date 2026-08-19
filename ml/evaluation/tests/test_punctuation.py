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
    MarkApplicationError,
    PunctuationDataset,
    apply_marks,
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


class TestApplyMarks:
    """The word-copy contract: original tokens verbatim, marks appended."""

    def test_words_are_copied_verbatim(self) -> None:
        text = "M16 rifle से pH GMT तक"
        out = apply_marks(text, [[], [], [], [","], [], [], [DANDA]])
        assert out == f"M16 rifle से, pH GMT तक{DANDA}"

    def test_the_invariant_holds_by_construction(self) -> None:
        # Every supported mark is category P: appending marks can never
        # change the depunct word sequence.
        cases = [
            "M16 राइफल से फायर किया",
            "site intelliai example com पर जाएँ",
            "support example com पर भेजिए",
            "डॉ शर्मा 400 AD से 1100 AD तक",
            "कुल 2500 रुपये और 2 5 प्रतिशत छूट",
        ]
        for text in cases:
            n = len(text.split())
            marks: list[list[str]] = [[] for _ in range(n + 1)]
            marks[-1] = [DANDA]
            if n > 2:
                marks[2] = [","]
            out = apply_marks(text, marks)
            assert invariant_holds(text, out), text
            assert "unk" not in out.casefold()

    def test_casing_is_untouched(self) -> None:
        out = apply_marks("Apple ने कहा", [[], [], [], [DANDA]])
        assert out.startswith("Apple ")

    def test_empty_text_yields_only_slot_zero(self) -> None:
        assert apply_marks("", [[]]) == ""
        assert apply_marks("   ", [[]]) == ""

    def test_marks_at_start_attach_before_the_first_token(self) -> None:
        assert apply_marks("ठीक", [[","], [DANDA]]) == f",ठीक{DANDA}"

    def test_whitespace_collapses_to_single_spaces(self) -> None:
        out = apply_marks("एक   दो\tतीन", [[], [], [], [DANDA]])
        assert out == f"एक दो तीन{DANDA}"

    def test_slot_count_mismatch_is_refused(self) -> None:
        with pytest.raises(MarkApplicationError):
            apply_marks("एक दो", [[], [DANDA]])

    def test_an_unsupported_mark_is_refused(self) -> None:
        with pytest.raises(MarkApplicationError):
            apply_marks("एक", [[], [";"]])

    def test_output_scores_perfectly_against_itself(self) -> None:
        text = "क्या आप कल आओगे"
        out = apply_marks(text, [[], [], [], [], ["?"]])
        pair = score_pair(out, out)
        assert pair.aligned
        assert pair.micro.f1 == 1.0


class TestV2RowFields:
    def test_domain_defaults_to_read_single_for_v1_rows(self) -> None:
        dataset = load_punctuation_dataset(MANIFEST)
        assert all(row.domain == "read-single" for row in dataset.rows)
        assert all(row.members == () for row in dataset.rows)


V2_MANIFEST = Path("ml/evaluation/punctuation/datasets/hi-punct-eval-v2.json")
ASR_EVAL = Path("ml/evaluation/stt/datasets/stt-hi-public-eval-v1.json")


class TestV2Manifest:
    """hi-punct-eval@v2: two domains, both reconstructible, both word-safe."""

    def test_the_v2_manifest_is_valid_and_pinned(self) -> None:
        dataset = load_punctuation_dataset(V2_MANIFEST)
        assert dataset.name == "hi-punct-eval"
        assert dataset.version == 2
        by_domain: dict[str, int] = {}
        for row in dataset.rows:
            by_domain[row.domain] = by_domain.get(row.domain, 0) + 1
        assert by_domain == {"read-paragraph": 88, "spontaneous": 60}

    def test_every_paragraph_is_reconstructible_from_its_members(self) -> None:
        # The derived component's law: paragraph text IS the space-join of
        # its member v1 rows, in order — no hand-written paragraphs.
        v1 = load_punctuation_dataset(MANIFEST)
        v1_text = {row.id: row.reference_text for row in v1.rows}
        v2 = load_punctuation_dataset(V2_MANIFEST)
        paragraphs = [row for row in v2.rows if row.domain == "read-paragraph"]
        assert paragraphs
        for row in paragraphs:
            assert len(row.members) == 3
            assert row.reference_text == " ".join(v1_text[m] for m in row.members)

    def test_every_spontaneous_annotation_preserves_the_source_words(self) -> None:
        # The annotation word law, pinned forever: punctuation was ADDED to
        # the frozen ASR eval reference — never a word changed.
        references = {
            clip["id"]: clip["reference_text"]
            for clip in json.loads(ASR_EVAL.read_text(encoding="utf-8"))["clips"]
        }
        v2 = load_punctuation_dataset(V2_MANIFEST)
        spontaneous = [row for row in v2.rows if row.domain == "spontaneous"]
        assert spontaneous
        for row in spontaneous:
            (clip_id,) = row.members
            assert depunct(row.reference_text) == depunct(references[clip_id]), clip_id

    def test_spontaneous_rows_keep_their_audio_identity(self) -> None:
        v2 = load_punctuation_dataset(V2_MANIFEST)
        for row in v2.rows:
            if row.domain == "spontaneous":
                assert row.source.files
                assert row.source.sentence_id == row.members[0]
