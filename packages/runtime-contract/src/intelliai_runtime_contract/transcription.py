"""Transcription capability schemas — the smallest surface that serves M2.

Fields are added when a real consumer needs them (additive-with-defaults,
ADR-0016), never speculatively. An empty `text` is a *valid* result: for
silence or non-speech audio, the correct transcription is nothing — the
evaluation seed's hallucination probes depend on runtimes being allowed to
say so.
"""

from __future__ import annotations

from pydantic import Field, model_validator

from intelliai_runtime_contract.base import ContractModel
from intelliai_runtime_contract.envelopes import RuntimeResponse


class TranscriptionRequest(ContractModel):
    """Capability params. The audio itself travels by transport, not here."""

    language: str | None = None  # BCP-47-ish hint; None = runtime auto-detects
    # The artifact identifier the gateway's registry resolved (never a public
    # model name, never an engine name). None = the runtime's default slot.
    # Added additively under contract v1 (ADR-0016 evolution rules).
    model: str | None = None


class TranscriptionSegment(ContractModel):
    """One timed span of recognized speech."""

    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    text: str

    @model_validator(mode="after")
    def _ordered(self) -> TranscriptionSegment:
        if self.end_seconds < self.start_seconds:
            msg = "segment end_seconds must be >= start_seconds"
            raise ValueError(msg)
        return self


class TranscriptionResult(ContractModel):
    """What the runtime heard. `language` is the detected (or confirmed)
    language; `duration_seconds` is the decoded audio length the usage
    accounting is based on."""

    text: str
    language: str = Field(min_length=1)
    duration_seconds: float = Field(ge=0)
    segments: tuple[TranscriptionSegment, ...] = ()
    # The pre-stage transcript when a text post-stage (e.g. punctuation
    # restoration) rewrote `text`; None when no stage changed anything.
    # The gateway stores it as the immutable original_transcript so
    # training provenance always carries the machine's RAW words.
    # Added additively under contract v1 (ADR-0016 evolution rules);
    # real consumer: the gateway's collection service (Milestone 30).
    raw_text: str | None = None


TranscriptionResponse = RuntimeResponse[TranscriptionResult]
