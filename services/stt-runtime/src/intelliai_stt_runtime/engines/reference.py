"""ReferenceEngine — the architecture's proof, not a toy.

A deterministic engine with no weights, no downloads, and no dependencies:
same audio in, same result out, on any machine, forever. It exists so that
the service, binding, lifecycle, and pool are all proven BEFORE the first
foundation model arrives (step 5) — and it stays forever as the engine the
test suite runs against, so CI never needs model weights (ADR-0003).

Its contract behavior is honest where it matters: silence produces an
EMPTY transcript — the hallucination-probe semantics the evaluation seed
measures real engines against.
"""

import hashlib
from typing import Final

from intelliai_runtime_contract import (
    TranscriptionRequest,
    TranscriptionResult,
    TranscriptionSegment,
)
from intelliai_stt_runtime.pipeline import DecodedAudio

ARTIFACT_ID: Final = "reference"


class ReferenceEngine:
    """Deterministic transcription: a digest-stamped description of the audio."""

    def transcribe(self, audio: DecodedAudio, request: TranscriptionRequest) -> TranscriptionResult:
        if audio.is_silence:
            # The correct transcription of silence is nothing (contract rule).
            return TranscriptionResult(
                text="",
                language=request.language or "zxx",
                duration_seconds=audio.duration_seconds,
            )
        digest = hashlib.sha256(audio.pcm).hexdigest()[:12]
        text = f"reference transcription of {audio.duration_seconds:.2f} seconds [{digest}]"
        return TranscriptionResult(
            text=text,
            language=request.language or "und",
            duration_seconds=audio.duration_seconds,
            segments=(
                TranscriptionSegment(
                    start_seconds=0.0,
                    end_seconds=audio.duration_seconds,
                    text=text,
                ),
            ),
        )

    def close(self) -> None:  # nothing to release; the protocol is the point
        return


def load_reference_engine() -> ReferenceEngine:
    """Slot loader: constructing the engine IS loading the model here."""
    return ReferenceEngine()
