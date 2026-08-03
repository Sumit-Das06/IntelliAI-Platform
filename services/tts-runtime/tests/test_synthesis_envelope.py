"""The envelope header ceiling — ADR-0020 invariant 2, pinned adversarially.

The happy-path test proves real envelopes fit; THIS test proves the
ceiling holds for a worst-plausible envelope: every operational field at
realistic maximum width. If a future field addition breaks this, the
addition must shrink or move to the body — the ceiling does not move up
casually (it is deliberately half of common 8 KB proxy header limits).
"""

from intelliai_runtime_contract import (
    RuntimeMetadata,
    RuntimeResponse,
    RuntimeTiming,
    SpeechSynthesisResult,
    Usage,
    UsageUnit,
)
from intelliai_tts_runtime.api.binding import MAX_ENVELOPE_HEADER_BYTES


def test_worst_plausible_envelope_fits_the_pinned_ceiling() -> None:
    envelope = RuntimeResponse[SpeechSynthesisResult](
        output=SpeechSynthesisResult(
            duration_seconds=35999.999999999996,  # ~10 hours, max float width
            sample_rate_hz=192_000,
            voice="intelliai-" + "x" * 54,  # a 64-char public voice id
            characters=999_999_999,
        ),
        model="x" * 64,  # a 64-char artifact identifier
        usage=(
            Usage(unit=UsageUnit.CHARACTERS, amount=999_999_999.999999),
            Usage(unit=UsageUnit.AUDIO_SECONDS, amount=35999.999999999996),
        ),
        timing=RuntimeTiming(
            total_ms=86_399_999.99999999,
            stages={
                # Twice today's stage count, with generously long names.
                f"a_very_long_stage_name_number_{i:02d}": 86_399_999.99999999
                for i in range(10)
            },
        ),
        runtime=RuntimeMetadata(
            service="x" * 32,
            service_version="10.20.30-rc.99+build.9999",
            contract_version=999,
        ),
    )
    wire = envelope.model_dump_json().encode("ascii")  # header values must be ascii-safe
    assert len(wire) <= MAX_ENVELOPE_HEADER_BYTES
