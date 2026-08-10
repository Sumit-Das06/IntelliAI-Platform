"""Probing is measured truth: WAV in, facts out, refusal otherwise."""

import io
import struct
import wave

import pytest

from intelliai_datasets.audio import (
    UnreadableAudioError,
    probe_audio,
    probe_wav,
    sha256_bytes,
)


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

    def test_flac_streaminfo_is_probed(self) -> None:
        # Minimal FLAC: marker + STREAMINFO(34 bytes) carrying 16 kHz mono,
        # 32000 total samples (= 2.0 s). Field packing per the FLAC spec.
        rate, total, bps = 16000, 32000, 16
        info = bytearray(34)
        info[10] = (rate >> 12) & 0xFF
        info[11] = (rate >> 4) & 0xFF
        # byte 12: rate low nibble | (channels-1)<<1 | top bit of (bps-1)
        info[12] = ((rate & 0xF) << 4) | ((1 - 1) << 1) | (((bps - 1) >> 4) & 1)
        # byte 13: low nibble of (bps-1) | top nibble of the 36-bit total
        info[13] = (((bps - 1) & 0xF) << 4) | ((total >> 32) & 0xF)
        info[14:18] = (total & 0xFFFFFFFF).to_bytes(4, "big")
        payload = b"fLaC" + bytes([0x00]) + (34).to_bytes(3, "big") + bytes(info)
        probe = probe_audio(payload)
        assert probe.container == "flac"
        assert probe.sample_rate_hz == rate
        assert probe.channels == 1
        assert probe.duration_seconds == pytest.approx(2.0)

    def test_probe_audio_dispatches_wav(self) -> None:
        probe = probe_audio(make_wav(seconds=1.0))
        assert probe.container == "wav"

    def test_unknown_container_is_refused(self) -> None:
        with pytest.raises(UnreadableAudioError, match="unrecognized container"):
            probe_audio(b"OggS" + b"\x00" * 64)

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
