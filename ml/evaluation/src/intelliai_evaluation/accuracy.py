"""The recognition accuracy family: one aligner, several rulers.

Every metric here reuses `wer.align_words` **unchanged**. Only the
normalisation and the granularity vary, which is what keeps WER and CER
internally consistent — they can never disagree about what the text was,
because CER is derived from the same tokens WER counted.

**Nothing here chooses a ruler.** Every function that normalises takes an
explicit :class:`NormalizationProfile`. That is not politeness, it is the
guard: the whole hazard this milestone exists to close is a reference
being scored by a ruler that was never chosen for it. A default parameter
would restore exactly that failure with a friendlier face.

`wer_ascii` is the exception that proves it: it *is* a ruler, frozen,
and it exists to keep the committed English baselines reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass

from intelliai_evaluation.normalization import ASCII_EN_V1, NormalizationProfile
from intelliai_evaluation.wer import WerBreakdown, align_words


class RulerFailureError(ValueError):
    """A declared reference normalised to nothing under the chosen ruler.

    This is the R-1 hazard, made loud. The corpus says the clip has words;
    the ruler disagrees; so the ruler is wrong for this text. Every number
    downstream would be plausible and false — a perfectly transcribed
    Hindi clip scores no WER at all, while a romanised or hallucinated one
    scores four "hallucinated words", because under an ASCII ruler the
    only thing being measured is how much Latin script the engine emitted.

    It raises rather than returning a sentinel because the founder ruling
    is explicit: this produces a Determination, never a numeric metric.
    B3 owns the record field; B2 owns making it impossible to ignore.
    """


@dataclass(frozen=True)
class AccuracyScores:
    """The whole §3.1 family for one (reference, hypothesis) pair.

    Word- and character-level breakdowns are kept side by side rather than
    aggregated: the rates are exactly additive with WER only because they
    share its denominator, and a caller that saw one number could not
    reconstruct that.
    """

    profile: str  # the ruler's `name@vN`, as an evidence record cites it
    words: WerBreakdown
    characters: WerBreakdown

    @property
    def wer(self) -> float:
        return self.words.wer

    @property
    def cer(self) -> float:
        return self.characters.wer

    @property
    def substitution_rate(self) -> float:
        return self.words.substitutions / self.words.reference_words

    @property
    def insertion_rate(self) -> float:
        return self.words.insertions / self.words.reference_words

    @property
    def deletion_rate(self) -> float:
        return self.words.deletions / self.words.reference_words

    @property
    def excess_word_ratio(self) -> float:
        """Over-generation as a symptom, never as proof of hallucination."""
        excess = max(0, self.words.hypothesis_words - self.words.reference_words)
        return excess / self.words.reference_words


def wer_ascii(reference: str, hypothesis: str) -> WerBreakdown:
    """The frozen English ruler — `ascii_en@v1`, unchanged since M2 step 0.

    Named for its ruler while the Unicode metrics are named for their
    computation, and the asymmetry is deliberate: this metric must stay
    self-identifying in records written *before* profiles existed, because
    it is the bridge to them. The Unicode metrics will never appear
    without a recorded profile, so they do not need to carry one in the
    name.
    """
    return _aligned(reference, hypothesis, ASCII_EN_V1, level="words")


def wer_unicode(reference: str, hypothesis: str, profile: NormalizationProfile) -> WerBreakdown:
    """Word error rate under an explicit Unicode-aware ruler."""
    return _aligned(reference, hypothesis, profile, level="words")


def cer_unicode(reference: str, hypothesis: str, profile: NormalizationProfile) -> WerBreakdown:
    """Character error rate under the same ruler, one granularity down.

    Primary for scripts where a word-level ruler cannot see the error:
    a Devanagari matra is sub-word, so a wrong matra is invisible to WER
    unless it changes the whole word, and Arabic clitic agglutination
    makes the orthographic word an unstable denominator.
    """
    return _aligned(reference, hypothesis, profile, level="characters")


def score(reference: str, hypothesis: str, profile: NormalizationProfile) -> AccuracyScores:
    """Both granularities under one ruler, computed once."""
    return AccuracyScores(
        profile=profile.id,
        words=_aligned(reference, hypothesis, profile, level="words"),
        characters=_aligned(reference, hypothesis, profile, level="characters"),
    )


def hallucinated_words(
    *, declared_reference: str, hypothesis: str, profile: NormalizationProfile
) -> int:
    """Words emitted where the **corpus manifest declares** an empty reference.

    "Declares", not "normalises to": the distinction is the entire metric.
    A probe clip whose manifest reference is ``""`` is asking what the
    system says when there is nothing to say, and the answer is evidence.
    A clip whose manifest reference has words but whose *normalised*
    reference is empty is not a hallucination measurement at all — it is a
    broken ruler, and it raises.
    """
    if declared_reference.strip():
        raise RulerFailureError(
            f"hallucinated_words is defined only where the corpus declares an empty "
            f"reference; this clip declares {declared_reference[:40]!r}. Measuring it "
            "here would count correct output as hallucination."
        )
    return len(profile.words(hypothesis))


def _aligned(
    reference: str, hypothesis: str, profile: NormalizationProfile, *, level: str
) -> WerBreakdown:
    """Normalise both sides with one ruler, then align — refusing a ruler
    that erased a reference somebody committed."""
    tokens = profile.words if level == "words" else profile.characters
    reference_tokens = tokens(reference)
    if reference.strip() and not reference_tokens:
        raise RulerFailureError(
            f"the corpus declares a reference ({reference[:40]!r}) that {profile.id} "
            f"normalises to nothing at the {level} level. The ruler is wrong for this "
            "text: every number computed from it would be plausible and false. Record "
            "a Determination, not a metric."
        )
    if not reference_tokens:
        raise RulerFailureError(
            "an empty reference has no error rate; measure hallucinated_words instead"
        )
    return align_words(reference_tokens, tokens(hypothesis))
