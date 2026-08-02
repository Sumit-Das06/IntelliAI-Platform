"""Word Error Rate — the transcription capability's primary quality metric.

Pure stdlib on purpose: the metric implementation must be trivially
auditable and dependency-stable for years — results are only comparable
if the ruler never moves. A changed metric is a NEW metric, never a
silent edit (module charter, question 6).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Lowercased text; everything except letters, digits, spaces, and
# apostrophes becomes a space. Apostrophes survive inside contractions
# ("don't") but are stripped from word edges.
_STRIP = re.compile(r"[^a-z0-9\s']+")


def normalize_words(text: str) -> list[str]:
    """Normalize text to the word list WER is computed over."""
    cleaned = _STRIP.sub(" ", text.lower())
    return [stripped for word in cleaned.split() if (stripped := word.strip("'"))]


@dataclass(frozen=True)
class WerBreakdown:
    """Edit-operation counts from aligning a hypothesis against a reference."""

    substitutions: int
    insertions: int
    deletions: int
    reference_words: int
    hypothesis_words: int

    @property
    def errors(self) -> int:
        return self.substitutions + self.insertions + self.deletions

    @property
    def wer(self) -> float:
        """errors / reference length. Undefined for empty references —
        empty-reference clips (silence probes) measure hallucinated words
        instead (see results.ClipResult)."""
        if self.reference_words == 0:
            msg = "WER is undefined for an empty reference; use hallucinated-word count"
            raise ValueError(msg)
        return self.errors / self.reference_words


def word_error_rate(reference: str, hypothesis: str) -> WerBreakdown:
    """Align normalized word sequences (Levenshtein) and count operations.

    Tie-breaking is deterministic (substitution over deletion over
    insertion at equal cost) so identical inputs always produce identical
    breakdowns across runs and machines.
    """
    ref = normalize_words(reference)
    hyp = normalize_words(hypothesis)

    # dp rows of (cost, substitutions, insertions, deletions)
    previous: list[tuple[int, int, int, int]] = [(j, 0, j, 0) for j in range(len(hyp) + 1)]

    for i in range(1, len(ref) + 1):
        current: list[tuple[int, int, int, int]] = [(i, 0, 0, i)]
        for j in range(1, len(hyp) + 1):
            if ref[i - 1] == hyp[j - 1]:
                cost, s, ins, dels = previous[j - 1]
                current.append((cost, s, ins, dels))
                continue
            sub_cost, sub_s, sub_i, sub_d = previous[j - 1]
            del_cost, del_s, del_i, del_d = previous[j]
            ins_cost, ins_s, ins_i, ins_d = current[j - 1]
            substitution = (sub_cost + 1, sub_s + 1, sub_i, sub_d)
            deletion = (del_cost + 1, del_s, del_i, del_d + 1)
            insertion = (ins_cost + 1, ins_s, ins_i + 1, ins_d)
            current.append(min((substitution, deletion, insertion), key=lambda t: t[0]))
        previous = current

    cost, substitutions, insertions, deletions = previous[len(hyp)]
    return WerBreakdown(
        substitutions=substitutions,
        insertions=insertions,
        deletions=deletions,
        reference_words=len(ref),
        hypothesis_words=len(hyp),
    )
