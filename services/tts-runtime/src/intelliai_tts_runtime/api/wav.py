"""PCM -> WAV containerization — the binding's job, never an engine's.

Engines produce canonical PCM and facts; the WAV container is transport
packaging (ADR-0020), so it lives in the api layer — the mirror image of
STT, where ffmpeg strips containers BEFORE engines. Stdlib only.
"""

import io
import wave

from intelliai_tts_runtime.engines import SynthesizedAudio


def encode_wav(audio: SynthesizedAudio) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(audio.sample_rate_hz)
        writer.writeframes(audio.pcm)
    return buffer.getvalue()
