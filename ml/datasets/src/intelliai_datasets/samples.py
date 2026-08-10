"""The one sample shape every source adapter produces.

Adapters differ; the stream they emit does not. Everything downstream
(validation, curation, manifests) is source-agnostic by construction.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CandidateSample(BaseModel):
    """One ingested clip, before validation."""

    model_config = ConfigDict(frozen=True)

    id: str  # stable, source-derived (e.g. "fleurs-hi-test-000123")
    source: str  # sources.SourceRecord.name
    language: str  # normalized base subtag ("hi", "zh", ...)
    split: str  # the SOURCE's official split ("train"/"validation"/"test")
    path: str  # relative to the data root, forward slashes
    text: str  # verbatim transcript as shipped by the source
    duration_seconds: float
    sample_rate_hz: int
    channels: int
    sha256: str
    speaker_id: str | None = None  # None = the source publishes none
    license: str = ""
    notes: str = ""
