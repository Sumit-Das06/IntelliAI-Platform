"""The TTS bench's pure parser: HTTP facts -> deterministic samples."""

import json

from intelliai_evaluation.bench_tts import sample_from_response


def envelope(synthesis_ms: float = 450.0, duration: float = 2.0) -> str:
    return json.dumps(
        {
            "output": {"duration_seconds": duration, "sample_rate_hz": 24000},
            "timing": {"total_ms": 500.0, "stages": {"synthesis": synthesis_ms}},
        }
    )


def test_success_sample_carries_synthesis_stage_and_audio_duration() -> None:
    sample = sample_from_response(200, envelope(), client_ms=520.0)
    assert sample.ok
    assert sample.synthesis_ms == 450.0
    assert sample.audio_seconds == 2.0


def test_missing_or_malformed_envelope_degrades_never_crashes() -> None:
    plain = sample_from_response(200, None, client_ms=100.0)
    assert plain.ok and plain.synthesis_ms is None  # gateway path: wall clock only
    garbage = sample_from_response(200, "not json", client_ms=100.0)
    assert garbage.ok and garbage.audio_seconds is None


def test_saturation_is_counted_not_hidden() -> None:
    refused = sample_from_response(503, None, client_ms=4.0)
    assert not refused.ok
    assert refused.status == 503
