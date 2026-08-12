"""The recognition accuracy family: one aligner, several rulers."""

from pathlib import Path

import pytest

from intelliai_evaluation.accuracy import (
    RulerFailureError,
    cer_unicode,
    hallucinated_words,
    score,
    wer_ascii,
    wer_unicode,
)
from intelliai_evaluation.dataset import find_dataset
from intelliai_evaluation.normalization import (
    ASCII_EN_V1,
    UNICODE_GENERIC_V2,
    profile_for,
)
from intelliai_evaluation.results import EvalRun
from intelliai_evaluation.wer import word_error_rate

HINDI = "मुझे हिंदी आती है"
RESULTS = Path("ml/evaluation/stt/results")
DATASETS = Path("ml/evaluation/stt/datasets")


def _reproduce(path: Path) -> int:
    """Recompute every ascii-anchored clip in a record; return how many matched."""
    run = EvalRun.model_validate_json(path.read_text(encoding="utf-8"))
    # By IDENTITY, never by filename — records cite name@vN, and non-seed
    # lineages (e.g. stt-hi-fleurs-eval) do not follow the seed's filename
    # pattern.
    dataset = find_dataset(DATASETS, run.dataset_name, run.dataset_version)
    references = {clip.id: clip.reference_text for clip in dataset.clips}

    # The anchor is English-only by construction: the runner emits
    # wer_ascii solely for `en` slices, so a non-English record carries no
    # ascii number to reproduce. (Its Devanagari references may still hold
    # stray ASCII tokens — digits, Latin loanwords — which the ascii ruler
    # would happily and wrongly "score".) Pinned count for such records: 0.
    declared = run.execution.declared_language if run.execution is not None else None
    if declared is not None and declared != "en":
        return 0

    matched = 0
    for clip in run.clips:
        reference = references[clip.clip_id]
        if not reference:  # probes declare no reference; nothing to align
            continue
        recomputed = wer_ascii(reference, clip.hypothesis_text)
        assert recomputed.substitutions == clip.substitutions
        assert recomputed.insertions == clip.insertions
        assert recomputed.deletions == clip.deletions
        assert recomputed.reference_words == clip.reference_words
        assert recomputed.hypothesis_words == clip.hypothesis_words
        matched += 1
    return matched


#: How many referenced clips each committed record contains. Pinned so the
#: reproduction above cannot quietly start checking nothing. Every record
#: that enters the ledger joins this table — an unlisted file fails loudly.
_WITH_REFERENCE = {
    "2026-08-02-whisper-small.json": 2,
    "2026-08-05-intelliai-stt-en.json": 2,
    "2026-08-05-intelliai-stt-hi.json": 0,  # no natural Hindi speech exists
    # PH0 apparatus validation (2026-08-06): en sessions carry the two JFK
    # clips; the probe-only slices carry none.
    "2026-08-06-intelliai-stt-en-whisper-small-int8-ph0.json": 2,
    "2026-08-06-intelliai-stt-en-whisper-small-int8-ph0-replicate.json": 2,
    "2026-08-06-intelliai-stt-hi-whisper-small-int8-ph0.json": 0,
    "2026-08-06-intelliai-stt-zxx-whisper-small-int8-ph0.json": 0,
    # Stage 1 Whisper family benchmark (2026-08-06): every en session
    # carries the two JFK clips.
    "2026-08-06-intelliai-stt-en-whisper-small-int8-stage1.json": 2,
    "2026-08-06-intelliai-stt-en-whisper-small-int8-stage1-replicate.json": 2,
    "2026-08-06-intelliai-stt-en-whisper-small-int8-stage1-r2.json": 2,
    "2026-08-06-research-whisper-base-en-whisper-base-int8-stage1.json": 2,
    "2026-08-06-research-whisper-base-en-whisper-base-int8-stage1-replicate.json": 2,
    "2026-08-06-research-whisper-large-v3-en-whisper-large-v3-int8-stage1.json": 2,
    "2026-08-06-research-whisper-large-v3-en-whisper-large-v3-int8-stage1-replicate.json": 2,
    # Milestone 15B (2026-08-11): the Hindi baseline record has natural
    # speech but NO ascii-anchored clips (wer_ascii is en-only), so its
    # reproduction count is 0 by construction, like the hi records above.
    "2026-08-11-intelliai-stt-hi-whisper-small-int8-15b-fleurs.json": 0,
    # Milestone 15C (2026-08-11): the official Hindi baseline + replicate
    # on stt-hi-public-eval@v1 — hi records, no ascii anchor, 0 by law.
    "2026-08-11-intelliai-stt-hi-whisper-small-int8-15c-public.json": 0,
    "2026-08-11-intelliai-stt-hi-whisper-small-int8-15c-public-replicate.json": 0,
    # Milestone 15D (2026-08-11): the E1 LoRA candidate. hi records carry
    # no ascii anchor (0 by law); the en regression record reproduces the
    # two JFK clips.
    "2026-08-11-research-whisper-small-hi-lora-e1-hi-15d.json": 0,
    "2026-08-11-research-whisper-small-hi-lora-e1-hi-15d-replicate.json": 0,
    "2026-08-11-research-whisper-small-hi-lora-e1-en-15d-regression.json": 2,
    # Milestone E1b (2026-08-12): Phase A swept the E1 run's earlier
    # checkpoints (all degraded); Phase B retrained conservatively
    # (lr 1e-4, 600 steps, best-val selection) and still failed the
    # benchmark. hi records carry no ascii anchor (0 by law); the en
    # regression record reproduces the two JFK clips.
    "2026-08-12-research-whisper-small-hi-lora-e1-ck500-hi-e1b-sweep.json": 0,
    "2026-08-12-research-whisper-small-hi-lora-e1-ck1000-hi-e1b-sweep.json": 0,
    "2026-08-12-research-whisper-small-hi-lora-e1-ck1500-hi-e1b-sweep.json": 0,
    "2026-08-12-research-whisper-small-hi-lora-e1b-hi-e1b.json": 0,
    "2026-08-12-research-whisper-small-hi-lora-e1b-hi-e1b-replicate.json": 0,
    "2026-08-12-research-whisper-small-hi-lora-e1b-en-e1b-regression.json": 2,
    # Milestone 15E (2026-08-12): Qwen3-ASR 0.6B behind the engine seam,
    # measured on the standard runner. hi and zh records carry no ascii
    # anchor (0 by law); the en record reproduces the two JFK clips.
    "2026-08-12-research-qwen3-asr-0.6b-hi-15e.json": 0,
    "2026-08-12-research-qwen3-asr-0.6b-hi-15e-replicate.json": 0,
    "2026-08-12-research-qwen3-asr-0.6b-en-15e.json": 2,
    "2026-08-12-research-qwen3-asr-0.6b-zh-15e.json": 0,
    # Milestone 16 (2026-08-12): the switching test — one multi-slot
    # process, per-language routes (hi → challenger, en → incumbent).
    # hi carries no ascii anchor (0 by law); the en arm runs on
    # whisper-small and reproduces the two JFK clips.
    "2026-08-12-research-intelliai-stt-switch-hi-16.json": 0,
    "2026-08-12-research-intelliai-stt-switch-en-16.json": 2,
    # Milestone 17 (2026-08-12): the pinned LINUX runtime validated on
    # the frozen primary (WSL2; hi record, no ascii anchor — 0 by law).
    "2026-08-12-research-qwen3-asr-0.6b-hi-17-linux.json": 0,
}


class TestWerAsciiIsTheLegacyAnchor:
    """It must reproduce every committed English number, forever."""

    def test_it_is_the_frozen_computation_itself(self) -> None:
        for reference, hypothesis in [
            ("and so my fellow americans", "and so my fellow americans"),
            ("ask not what your country can do", "ask not what your country can"),
            ("Hello, World!", "hello world"),
            ("don't stop", "do not stop"),
        ]:
            assert wer_ascii(reference, hypothesis) == word_error_rate(reference, hypothesis)

    @pytest.mark.parametrize("path", sorted(RESULTS.glob("*.json")), ids=lambda p: p.name)
    def test_it_reproduces_the_committed_baseline_exactly(self, path: Path) -> None:
        """Recompute each committed clip from the record's own text.

        This is the compatibility claim, checked rather than asserted: the
        record stores the hypothesis verbatim, so every alignment count can
        be recomputed and must match to the integer.
        """
        assert _reproduce(path) == _WITH_REFERENCE[path.name]

    def test_the_reproduction_actually_checked_something(self) -> None:
        # A guard on the guard: the Hindi record has no natural speech, so
        # its reproduction is vacuously true. If the English records ever
        # stopped contributing clips, every assertion above would pass
        # while proving nothing.
        assert sum(_WITH_REFERENCE.values()) == 30


class TestUnicodeRulersNeverChooseThemselves:
    """Every Unicode computation takes an explicit profile.

    A default would restore the exact hazard this milestone closes: a
    reference scored by a ruler nobody chose for it.
    """

    def test_wer_unicode_scores_a_perfect_hindi_transcript_as_perfect(self) -> None:
        breakdown = wer_unicode(HINDI, HINDI, profile_for("hi"))
        assert breakdown.reference_words == 4
        assert breakdown.wer == 0.0

    def test_the_same_text_under_the_ascii_ruler_is_a_ruler_failure(self) -> None:
        # Before B2 this silently produced wer=None and turned the metric
        # into a Latin-script detector. Now it cannot be computed at all.
        with pytest.raises(RulerFailureError, match="normalises to nothing"):
            wer_unicode(HINDI, HINDI, ASCII_EN_V1)

    def test_cer_sees_a_matra_error_that_wer_cannot(self) -> None:
        # हिंदी -> हिन्दी changes one word entirely at word level (WER 0.25)
        # but only a little at character level: the point of a co-primary.
        wrong = "मुझे हिन्दी आती है"
        words = wer_unicode(HINDI, wrong, UNICODE_GENERIC_V2)
        chars = cer_unicode(HINDI, wrong, UNICODE_GENERIC_V2)
        assert words.wer == 0.25
        assert 0.0 < chars.wer < words.wer

    def test_score_computes_both_granularities_under_one_ruler(self) -> None:
        scores = score(HINDI, HINDI, profile_for("hi"))
        assert scores.profile == "unicode_generic@v2"
        assert scores.wer == 0.0
        assert scores.cer == 0.0


class TestRates:
    def test_they_share_wer_s_denominator_so_they_are_additive_with_it(self) -> None:
        scores = score("a b c d", "a x c", UNICODE_GENERIC_V2)
        total = scores.substitution_rate + scores.insertion_rate + scores.deletion_rate
        assert total == pytest.approx(scores.wer)

    def test_excess_word_ratio_is_zero_when_nothing_is_over_generated(self) -> None:
        assert score("a b c", "a b", UNICODE_GENERIC_V2).excess_word_ratio == 0.0

    def test_excess_word_ratio_measures_over_generation_only(self) -> None:
        assert score("a b", "a b c d", UNICODE_GENERIC_V2).excess_word_ratio == 1.0


class TestHallucinatedWords:
    """Declared empty, never normalised-to-empty. This is the whole metric."""

    def test_it_counts_output_where_the_corpus_declares_silence(self) -> None:
        assert (
            hallucinated_words(
                declared_reference="",
                hypothesis="subscribe to the channel",
                profile=UNICODE_GENERIC_V2,
            )
            == 4
        )

    def test_silence_answered_with_silence_is_zero(self) -> None:
        assert (
            hallucinated_words(declared_reference="", hypothesis="", profile=UNICODE_GENERIC_V2)
            == 0
        )

    def test_a_declared_reference_is_refused_even_under_a_ruler_that_erases_it(self) -> None:
        # The pre-B2 behaviour: a Hindi clip under the ASCII ruler had
        # reference_words == 0, so a romanised or hallucinated transcript
        # scored N "hallucinated words" while a PERFECT one scored 0. The
        # metric measured how much Latin the engine emitted. It now raises.
        with pytest.raises(RulerFailureError, match="declares an empty reference"):
            hallucinated_words(
                declared_reference=HINDI, hypothesis="mujhe hindi aati hai", profile=ASCII_EN_V1
            )

    def test_it_is_refused_for_a_declared_reference_under_any_ruler(self) -> None:
        with pytest.raises(RulerFailureError):
            hallucinated_words(
                declared_reference="hello world", hypothesis="hello", profile=UNICODE_GENERIC_V2
            )


class TestRulerFailureIsNeverANumber:
    """Founder ruling: a ruler failure produces a Determination, not a metric."""

    @pytest.mark.parametrize("compute", [wer_unicode, cer_unicode])
    def test_an_erased_reference_raises_instead_of_scoring(self, compute: object) -> None:
        with pytest.raises(RulerFailureError, match="Record a Determination, not a metric"):
            compute(HINDI, HINDI, ASCII_EN_V1)  # type: ignore[operator]

    def test_the_refusal_names_the_ruler_so_the_fix_is_obvious(self) -> None:
        with pytest.raises(RulerFailureError, match="ascii_en@v1"):
            wer_unicode(HINDI, HINDI, ASCII_EN_V1)

    def test_an_empty_reference_has_no_error_rate(self) -> None:
        with pytest.raises(RulerFailureError, match="measure hallucinated_words instead"):
            wer_unicode("", "anything", UNICODE_GENERIC_V2)
