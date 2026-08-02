"""Benchmark result records — the format every model measurement is kept in.

One EvalRun per (dataset version, artifact, build) measurement, serialized
to JSON and committed under the capability's results/ directory
(append-only, never edited — Constitution P13). The schema is
additive-only: consumers written today must parse results written in five
years.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ClipResult(BaseModel):
    """Measurement for one clip within a run."""

    model_config = ConfigDict(frozen=True)

    clip_id: str
    duration_seconds: float
    inference_seconds: float
    substitutions: int
    insertions: int
    deletions: int
    reference_words: int
    hypothesis_words: int
    hypothesis_text: str

    @property
    def errors(self) -> int:
        return self.substitutions + self.insertions + self.deletions

    @property
    def wer(self) -> float | None:
        """None for empty-reference probes (their metric is hallucination)."""
        if self.reference_words == 0:
            return None
        return self.errors / self.reference_words

    @property
    def hallucinated_words(self) -> int:
        """Words emitted where the correct output was silence."""
        return self.hypothesis_words if self.reference_words == 0 else 0

    @property
    def rtf(self) -> float:
        """Real-time factor: inference time / audio duration (lower is better)."""
        return self.inference_seconds / self.duration_seconds


class EvalRun(BaseModel):
    """One complete measurement of one model against one dataset version."""

    model_config = ConfigDict(frozen=True)

    dataset_name: str
    dataset_version: int
    capability: str
    run_at: datetime
    artifact: str  # registry model id (e.g. "whisper-small")
    engine: str
    engine_version: str
    compute: str  # e.g. "cpu-int8"
    hardware: str  # human description of the machine
    notes: str = ""
    clips: list[ClipResult]

    @property
    def overall_wer(self) -> float | None:
        """Word-weighted WER across clips with non-empty references."""
        reference_total = sum(c.reference_words for c in self.clips)
        if reference_total == 0:
            return None
        error_total = sum(c.errors for c in self.clips if c.reference_words > 0)
        return error_total / reference_total

    @property
    def mean_rtf(self) -> float | None:
        if not self.clips:
            return None
        return sum(c.rtf for c in self.clips) / len(self.clips)

    @property
    def hallucinated_words_total(self) -> int:
        return sum(c.hallucinated_words for c in self.clips)

    def summary(self) -> dict[str, object]:
        """Compact aggregate view for logs and review tables."""
        return {
            "dataset": f"{self.dataset_name}@v{self.dataset_version}",
            "artifact": self.artifact,
            "engine": f"{self.engine} {self.engine_version}",
            "compute": self.compute,
            "overall_wer": self.overall_wer,
            "mean_rtf": self.mean_rtf,
            "hallucinated_words_total": self.hallucinated_words_total,
            "clips": len(self.clips),
        }
