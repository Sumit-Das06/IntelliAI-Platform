"""Minimal WAV decoding (stdlib only) — the step-3 slice of the pipeline."""

import io
import wave
from dataclasses import dataclass

from intelliai_runtime_contract import RuntimeErrorType
from intelliai_stt_runtime.failures import RuntimeServiceError


@dataclass(frozen=True)
class DecodedAudio:
    """What engines receive: decoded PCM plus the facts about it."""

    pcm: bytes
    sample_rate_hz: int
    channels: int
    sample_width_bytes: int
    duration_seconds: float

    @property
    def is_silence(self) -> bool:
        """True when every sample is digital zero (8-bit WAV zero is 0x80)."""
        if not self.pcm:
            return True
        zero = 0x80 if self.sample_width_bytes == 1 else 0x00
        return all(byte == zero for byte in self.pcm)


def decode_wav(payload: bytes) -> DecodedAudio:
    """Decode a WAV container or refuse with a contract-shaped failure.

    Only WAV is accepted until the full media pipeline lands (M2 step 4:
    sniff -> ffmpeg -> 16 kHz mono -> VAD)."""
    try:
        with wave.open(io.BytesIO(payload)) as reader:
            sample_rate = reader.getframerate()
            channels = reader.getnchannels()
            sample_width = reader.getsampwidth()
            frame_count = reader.getnframes()
            pcm = reader.readframes(frame_count)
    except (wave.Error, EOFError) as exc:
        raise RuntimeServiceError(
            RuntimeErrorType.INVALID_INPUT,
            "audio must be a WAV file (further containers arrive with the media pipeline)",
            param="file",
        ) from exc
    if sample_rate <= 0:
        raise RuntimeServiceError(
            RuntimeErrorType.INVALID_INPUT,
            "WAV header declares an invalid sample rate",
            param="file",
        )
    return DecodedAudio(
        pcm=pcm,
        sample_rate_hz=sample_rate,
        channels=channels,
        sample_width_bytes=sample_width,
        duration_seconds=frame_count / sample_rate,
    )
