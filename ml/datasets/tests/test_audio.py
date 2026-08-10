"""Probing is measured truth: WAV in, facts out, refusal otherwise."""

import io
import struct
import wave

import pytest

from intelliai_datasets.audio import UnreadableAudioError, probe_wav, sha256_bytes


def make_wav(seconds: float = 1.0, rate: int = 16000, channels: int = 1) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(2)
        writer.setframerate(rate)
        writer.writeframes(b"\x01\x00" * int(seconds * rate) * channels)
    return buffer.getvalue()


class TestProbe:
    def test_probe_reads_wav_facts(self) -> None:
        probe = probe_wav(make_wav(seconds=2.0, rate=16000))
        assert probe.container == "wav"
        assert probe.sample_rate_hz == 16000
        assert probe.channels == 1
        assert probe.duration_seconds == pytest.approx(2.0)
        assert probe.sha256 == sha256_bytes(make_wav(seconds=2.0, rate=16000))

    def test_ieee_float_wav_is_probed(self) -> None:
        # FLEURS parquet ships format-3 (IEEE float) WAV, which the stdlib
        # wave module refuses — the probe must read it.
        rate, seconds = 16000, 1.5
        frames = b"\x00\x00\x80\x3f" * int(rate * seconds)  # 1.0f per frame
        fmt = struct.pack("<HHIIHH", 3, 1, rate, rate * 4, 4, 32)
        payload = (
            b"RIFF"
            + struct.pack("<I", 4 + 8 + len(fmt) + 8 + len(frames))
            + b"WAVE"
            + b"fmt "
            + struct.pack("<I", len(fmt))
            + fmt
            + b"data"
            + struct.pack("<I", len(frames))
            + frames
        )
        probe = probe_wav(payload)
        assert probe.sample_rate_hz == rate
        assert probe.channels == 1
        assert probe.duration_seconds == pytest.approx(seconds)

    def test_non_riff_bytes_are_refused(self) -> None:
        with pytest.raises(UnreadableAudioError, match="RIFF"):
            probe_wav(b"fLaC not a wav" + b"\x00" * 16)

    def test_unsupported_format_code_is_refused(self) -> None:
        fmt = struct.pack("<HHIIHH", 6, 1, 8000, 8000, 1, 8)  # A-law
        payload = (
            b"RIFF"
            + struct.pack("<I", 4 + 8 + len(fmt) + 8 + 8)
            + b"WAVE"
            + b"fmt "
            + struct.pack("<I", len(fmt))
            + fmt
            + b"data"
            + struct.pack("<I", 8)
            + b"\x00" * 8
        )
        with pytest.raises(UnreadableAudioError, match="format code 6"):
            probe_wav(payload)

    def test_truncated_wav_is_refused(self) -> None:
        with pytest.raises(UnreadableAudioError):
            probe_wav(make_wav()[:16])
