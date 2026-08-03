"""ReferenceSynthesisEngine — the architecture's proof, not a toy.

A deterministic engine with no weights, no downloads, and no dependencies:
same (text, voice, speed) in, same PCM out, on any machine, forever. It
exists so that the service, binary binding, lifecycle, and pool are all
proven BEFORE the first foundation model arrives (step 4) — and it stays
forever as the engine the test suite runs against, so CI never needs
model weights (ADR-0003).

Its output is honest where it matters: audio depends on the TEXT (each
character renders as a short chromatic tone off the voice's base pitch),
on the VOICE (base frequency), and on SPEED (per-character duration) — so
usage accounting, duration proportionality, and voice/speed plumbing are
all measurable facts, not mocks.
"""

import math
from typing import Final

from intelliai_tts_runtime.engines.base import SynthesizedAudio

ARTIFACT_ID: Final = "reference"

SAMPLE_RATE_HZ: Final = 24_000
_SECONDS_PER_CHAR: Final = 0.05
_AMPLITUDE: Final = 0.3  # comfortable, nowhere near clipping


class ReferenceSynthesisEngine:
    """Deterministic synthesis: a tone sequence derived from the text."""

    def synthesize(self, text: str, voice: str, speed: float | None) -> SynthesizedAudio:
        base_hz = float(voice.removeprefix("tone:"))
        seconds_per_char = _SECONDS_PER_CHAR / (speed if speed is not None else 1.0)
        samples_per_char = max(1, int(SAMPLE_RATE_HZ * seconds_per_char))

        pcm = bytearray()
        for char in text:
            # One chromatic step per character code: text changes the audio.
            frequency = base_hz * 2 ** ((ord(char) % 12) / 12)
            for i in range(samples_per_char):
                value = _AMPLITUDE * math.sin(2 * math.pi * frequency * i / SAMPLE_RATE_HZ)
                pcm += int(value * 32767).to_bytes(2, "little", signed=True)
        return SynthesizedAudio(pcm=bytes(pcm), sample_rate_hz=SAMPLE_RATE_HZ)

    def close(self) -> None:  # nothing to release; the protocol is the point
        return


def load_reference_synthesis_engine() -> ReferenceSynthesisEngine:
    """Slot loader: constructing the engine IS loading the model here."""
    return ReferenceSynthesisEngine()
