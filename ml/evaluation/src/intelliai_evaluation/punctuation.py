"""Punctuation-restoration scoring: one slot ruler, several counted marks.

The law of this module: punctuation quality is judged WITHOUT touching the
frozen accuracy rulers. The registered normalization profiles delete
punctuation by design (category P becomes a space), so CER/WER are and stay
punctuation-blind. This module is the separate lens: it extracts words and
the punctuation SLOTS between them, and scores predicted marks against
reference marks position by position.

Ruler identity: ``punct_slots@v1`` (PUNCTUATION_RULER). Its transform:
NFC -> casefold -> format characters (Cf) DELETED (the unicode_generic@v2
lesson: Cf-to-space splits conjuncts) -> every other category-P character
becomes a SPACE -> whitespace collapsed. Words are the non-punctuation
runs; slot ``i`` holds the supported marks seen after word ``i`` (slot 0 is
the rare before-any-word position). Marks outside SUPPORTED_MARKS are
ignored by scoring on BOTH sides — symmetrically, so quotes, parentheses,
hyphens and other unscored punctuation can never flip a verdict.

Two deliberate policies, documented rather than hidden:

* "." and "।" are DIFFERENT marks in per-mark scores, but both belong to
  the SENTENCE_END group for boundary scoring — FLEURS Hindi mixes them as
  sentence enders, and pretending they are always semantically different
  would punish a restorer for the source's own style drift.
* The safety invariant (``invariant_holds``) is a GATE, not a metric: a
  punctuation output that changes any word is unsafe, is excluded from
  mark counting, and must fail the run it appears in.

Like every ruler in this plane: a changed transform is a NEW ruler name,
never an edit to this one.
"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator

#: Ruler identity for evidence records. Frozen once cited by committed
#: evidence; a different transform is a different name.
PUNCTUATION_RULER = "punct_slots@v1"

#: The marks scoring counts, each by itself. Everything else is ignored.
SUPPORTED_MARKS: tuple[str, ...] = ("।", ",", "?", "!", ".")

#: The sentence-boundary group: any of these ends a sentence. "." and "।"
#: stay distinct per-mark; here they count as the same event.
SENTENCE_END_MARKS: frozenset[str] = frozenset({"।", "?", "!", "."})


def _is_punct(ch: str) -> bool:
    return unicodedata.category(ch).startswith("P")


def _is_format(ch: str) -> bool:
    return unicodedata.category(ch) == "Cf"


def depunct(text: str) -> str:
    """The invariant transform: what the words are, punctuation aside.

    NFC -> casefold -> Cf deleted -> category P -> space -> collapse.
    """
    folded = unicodedata.normalize("NFC", text).casefold()
    kept: list[str] = []
    for ch in folded:
        if _is_format(ch):
            continue
        kept.append(" " if _is_punct(ch) else ch)
    return " ".join("".join(kept).split())


def strip_punctuation_for_input(text: str) -> str:
    """Reference -> restorer input: punctuation removed, CASE PRESERVED.

    NFC -> Cf deleted -> category P -> space -> whitespace collapsed. This
    is the text-level benchmark's input preparation; it deliberately keeps
    case (our ASR emits cased text) while ``depunct`` casefolds for the
    safety comparison.
    """
    composed = unicodedata.normalize("NFC", text)
    kept: list[str] = []
    for ch in composed:
        if _is_format(ch):
            continue
        kept.append(" " if _is_punct(ch) else ch)
    return " ".join("".join(kept).split())


@dataclass(frozen=True)
class Extraction:
    """Words plus the punctuation slots around them.

    ``slots`` has ``len(words) + 1`` entries: ``slots[0]`` holds supported
    marks seen before any word; ``slots[i]`` holds the marks after word
    ``i`` (1-based). Each slot is the ordered tuple of marks as they
    appeared; scoring treats it as a multiset.
    """

    words: tuple[str, ...]
    slots: tuple[tuple[str, ...], ...]


def extract(text: str) -> Extraction:
    """Split ``text`` into depunct words and per-slot supported marks."""
    folded = unicodedata.normalize("NFC", text).casefold()
    words: list[str] = []
    slots: list[list[str]] = [[]]
    current: list[str] = []

    def close_word() -> None:
        if current:
            words.append("".join(current))
            slots.append([])
            current.clear()

    for ch in folded:
        if _is_format(ch):
            continue
        if ch.isspace():
            close_word()
        elif _is_punct(ch):
            close_word()
            if ch in SUPPORTED_MARKS:
                slots[-1].append(ch)
        else:
            current.append(ch)
    close_word()
    return Extraction(
        words=tuple(words),
        slots=tuple(tuple(slot) for slot in slots),
    )


def invariant_holds(input_text: str, output_text: str) -> bool:
    """The hard safety gate: punctuation may be added, words may not change."""
    return depunct(input_text) == depunct(output_text)


@dataclass
class Counts:
    """Micro counts with the degenerate-zero convention made explicit.

    When nothing was predicted, precision is 0.0 (not undefined); when
    nothing was expected, recall is 0.0; F1 is 0.0 whenever either is.
    """

    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    @property
    def precision(self) -> float:
        predicted = self.true_positives + self.false_positives
        return self.true_positives / predicted if predicted else 0.0

    @property
    def recall(self) -> float:
        expected = self.true_positives + self.false_negatives
        return self.true_positives / expected if expected else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    def add(self, other: Counts) -> None:
        self.true_positives += other.true_positives
        self.false_positives += other.false_positives
        self.false_negatives += other.false_negatives

    def as_dict(self) -> dict[str, float | int]:
        return {
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
        }


@dataclass
class PairScore:
    """One reference/prediction pair, scored — or refused as unsafe."""

    aligned: bool
    micro: Counts = field(default_factory=Counts)
    per_mark: dict[str, Counts] = field(default_factory=dict)
    boundary: Counts = field(default_factory=Counts)


def _slot_counts(reference: tuple[str, ...], predicted: tuple[str, ...]) -> dict[str, Counts]:
    per_mark: dict[str, Counts] = {}
    for mark in SUPPORTED_MARKS:
        ref_n = reference.count(mark)
        pred_n = predicted.count(mark)
        agree = min(ref_n, pred_n)
        per_mark[mark] = Counts(
            true_positives=agree,
            false_positives=pred_n - agree,
            false_negatives=ref_n - agree,
        )
    return per_mark


def score_pair(reference_text: str, predicted_text: str) -> PairScore:
    """Score one prediction against one punctuated reference.

    If the two texts disagree on WORDS (the invariant), the pair is
    unaligned: no mark is counted, and the caller must treat the row as an
    invariant failure — never silently repair it.
    """
    reference = extract(reference_text)
    predicted = extract(predicted_text)
    if reference.words != predicted.words:
        return PairScore(aligned=False)

    score = PairScore(aligned=True, per_mark={mark: Counts() for mark in SUPPORTED_MARKS})
    for ref_slot, pred_slot in zip(reference.slots, predicted.slots, strict=True):
        for mark, counts in _slot_counts(ref_slot, pred_slot).items():
            score.per_mark[mark].add(counts)
            score.micro.add(counts)
        ref_boundary = any(mark in SENTENCE_END_MARKS for mark in ref_slot)
        pred_boundary = any(mark in SENTENCE_END_MARKS for mark in pred_slot)
        if ref_boundary and pred_boundary:
            score.boundary.add(Counts(true_positives=1))
        elif pred_boundary:
            score.boundary.add(Counts(false_positives=1))
        elif ref_boundary:
            score.boundary.add(Counts(false_negatives=1))
    return score


@dataclass
class CorpusScore:
    """Aggregate over a whole evaluation: counts plus the safety verdict."""

    rows: int = 0
    aligned_rows: int = 0
    invariant_failures: int = 0
    micro: Counts = field(default_factory=Counts)
    per_mark: dict[str, Counts] = field(
        default_factory=lambda: {mark: Counts() for mark in SUPPORTED_MARKS}
    )
    boundary: Counts = field(default_factory=Counts)

    @property
    def invariant_pass_rate(self) -> float:
        return self.aligned_rows / self.rows if self.rows else 0.0

    def as_dict(self) -> dict[str, object]:
        return {
            "ruler": PUNCTUATION_RULER,
            "rows": self.rows,
            "aligned_rows": self.aligned_rows,
            "invariant_failures": self.invariant_failures,
            "invariant_pass_rate": round(self.invariant_pass_rate, 4),
            "micro": self.micro.as_dict(),
            "per_mark": {mark: counts.as_dict() for mark, counts in self.per_mark.items()},
            "sentence_boundary": self.boundary.as_dict(),
        }


def score_corpus(pairs: list[tuple[str, str]]) -> CorpusScore:
    """Score (reference_text, predicted_text) pairs; unsafe rows count, not score."""
    corpus = CorpusScore()
    for reference_text, predicted_text in pairs:
        corpus.rows += 1
        pair = score_pair(reference_text, predicted_text)
        if not pair.aligned:
            corpus.invariant_failures += 1
            continue
        corpus.aligned_rows += 1
        corpus.micro.add(pair.micro)
        for mark, counts in pair.per_mark.items():
            corpus.per_mark[mark].add(counts)
        corpus.boundary.add(pair.boundary)
    return corpus


# ── Dataset manifest (text-level punctuation benchmark) ──────────────────


class PunctuationSourceAudio(BaseModel):
    """The source recordings behind one reference text (not vendored here)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sentence_id: str
    files: tuple[str, ...]
    genders: tuple[str, ...]
    duration_seconds: tuple[float, ...]


class PunctuationRow(BaseModel):
    """One punctuated reference. The audio stays at the pinned source."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    language: str
    reference_text: str
    source: PunctuationSourceAudio

    @field_validator("reference_text")
    @classmethod
    def _normalized_and_nonempty(cls, value: str) -> str:
        if not value.strip():
            msg = "reference_text must not be empty"
            raise ValueError(msg)
        if value != " ".join(unicodedata.normalize("NFC", value).split()):
            msg = "reference_text must be NFC-normalized with collapsed whitespace"
            raise ValueError(msg)
        return value


class PunctuationDataset(BaseModel):
    """A frozen text-level punctuation benchmark. Released versions are
    immutable; changes create the next version."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    version: int
    task: str
    description: str
    rows: tuple[PunctuationRow, ...]

    @field_validator("task")
    @classmethod
    def _task_is_punctuation(cls, value: str) -> str:
        if value != "punctuation-restoration":
            msg = f"unsupported task: {value!r}"
            raise ValueError(msg)
        return value

    @field_validator("rows")
    @classmethod
    def _ids_unique(cls, value: tuple[PunctuationRow, ...]) -> tuple[PunctuationRow, ...]:
        ids = [row.id for row in value]
        if len(set(ids)) != len(ids):
            msg = "row ids must be unique"
            raise ValueError(msg)
        return value


def load_punctuation_dataset(path: Path) -> PunctuationDataset:
    """Load and validate a punctuation benchmark manifest."""
    return PunctuationDataset.model_validate(json.loads(path.read_text(encoding="utf-8")))
