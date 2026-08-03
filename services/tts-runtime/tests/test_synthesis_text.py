"""The text pipeline: validation limits, the normalize seam, stage timing."""

import pytest

from intelliai_runtime_contract import RuntimeErrorType
from intelliai_runtime_core import RuntimeServiceError
from intelliai_tts_runtime.pipeline import TextPipeline


def test_passes_text_through_with_stage_timings() -> None:
    output = TextPipeline(max_text_chars=100).process("hello")
    assert output.text == "hello"  # normalize is a pass-through seam in v1
    assert set(output.timings_ms) == {"validate", "normalize"}


def test_over_limit_text_is_invalid_input_with_param() -> None:
    with pytest.raises(RuntimeServiceError) as exc_info:
        TextPipeline(max_text_chars=5).process("x" * 6)
    assert exc_info.value.error_type is RuntimeErrorType.INVALID_INPUT
    assert exc_info.value.param == "text"


def test_limit_is_inclusive() -> None:
    assert TextPipeline(max_text_chars=5).process("x" * 5).text == "x" * 5
