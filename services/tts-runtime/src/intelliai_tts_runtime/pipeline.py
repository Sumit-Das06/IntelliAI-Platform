"""The text pipeline: validate -> normalize -> handoff, every stage timed.

The synthesis mirror of STT's media pipeline, deliberately small: text
needs no decoding, but the pipeline SHAPE is the same — engine-independent
ingestion that engines never see past. ``normalize`` is a reserved seam:
v1 passes text through untouched; future text normalization (numbers,
abbreviations, units) lives HERE, never inside engines, so every engine
benefits and normalization changes never touch model adapters.

Length limits are runtime policy (config), not contract vocabulary: the
contract requires non-empty text; how much text one request may carry is
deployment business. Over-limit answers ``invalid_input`` before any
engine runs.
"""

import time
from dataclasses import dataclass

from intelliai_runtime_contract import RuntimeErrorType
from intelliai_runtime_core import RuntimeServiceError


@dataclass(frozen=True)
class TextOutput:
    """What the pipeline hands to synthesis: canonical text plus stage facts."""

    text: str
    timings_ms: dict[str, float]


class TextPipeline:
    def __init__(self, max_text_chars: int) -> None:
        self._max_text_chars = max_text_chars

    def process(self, text: str) -> TextOutput:
        timings: dict[str, float] = {}

        started = time.perf_counter()
        if len(text) > self._max_text_chars:
            raise RuntimeServiceError(
                RuntimeErrorType.INVALID_INPUT,
                f"text exceeds the {self._max_text_chars}-character limit",
                param="text",
            )
        timings["validate"] = (time.perf_counter() - started) * 1000.0

        started = time.perf_counter()
        normalized = text  # the reserved seam: v1 is pass-through by design
        timings["normalize"] = (time.perf_counter() - started) * 1000.0

        return TextOutput(text=normalized, timings_ms=timings)
