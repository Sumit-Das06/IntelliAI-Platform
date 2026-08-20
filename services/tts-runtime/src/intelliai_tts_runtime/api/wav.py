"""PCM -> WAV containerization — the binding's job, never an engine's.

Engines produce canonical PCM and facts; the WAV container is transport
packaging (ADR-0020), so it lives in the api layer — the mirror image of
STT, where ffmpeg strips containers BEFORE engines. Stdlib only.
"""

import io
import struct
import wave

from intelliai_tts_runtime.engines import SynthesizedAudio

#: The size fields a streaming WAV cannot know. Writing the maximum is
#: the long-standing streaming-WAV convention: players that trust sizes
#: read to end-of-stream anyway, and OUR web client parses only the
#: 44-byte preamble for format facts, never for length.
_UNKNOWN_SIZE = 0xFFFFFFFF


def encode_wav(audio: SynthesizedAudio) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(audio.sample_rate_hz)
        writer.writeframes(audio.pcm)
    return buffer.getvalue()


def streaming_wav_header(sample_rate_hz: int) -> bytes:
    """A standard 44-byte PCM16-mono WAV header with unknown-length size
    fields (M36): sent once, before the first audio chunk, so the byte
    stream is 'a WAV that is still being written'. Format facts (rate,
    channels, width) are exact; only the two size fields are the
    streaming placeholder."""
    byte_rate = sample_rate_hz * 2  # mono, 16-bit
    return b"".join(
        (
            b"RIFF",
            struct.pack("<I", _UNKNOWN_SIZE),
            b"WAVE",
            b"fmt ",
            struct.pack("<IHHIIHH", 16, 1, 1, sample_rate_hz, byte_rate, 2, 16),
            b"data",
            struct.pack("<I", _UNKNOWN_SIZE),
        )
    )
