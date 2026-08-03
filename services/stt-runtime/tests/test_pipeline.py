"""The pipeline end to end, against a real ffmpeg (installed in CI).

The FLAC fixture is encoded by ffmpeg itself: proof that a compressed
container normalizes to the same canonical audio as WAV.
"""

import subprocess
from pathlib import Path

import pytest

from helpers import wav_bytes
from intelliai_runtime_contract import RuntimeErrorType
from intelliai_stt_runtime.failures import RuntimeServiceError
from intelliai_stt_runtime.pipeline import (
    CANONICAL_SAMPLE_RATE_HZ,
    EnergyVad,
    FfmpegDecoder,
    MediaFormat,
    MediaPipeline,
)

STAGES = ("validate", "detect", "decode", "normalize", "vad")


def make_pipeline(
    *, max_upload_bytes: int = 25 * 1024 * 1024, max_audio_seconds: float = 600.0
) -> MediaPipeline:
    return MediaPipeline(
        FfmpegDecoder("ffmpeg", 30.0),
        EnergyVad(),
        max_upload_bytes=max_upload_bytes,
        max_audio_seconds=max_audio_seconds,
    )


def encode_flac(wav: bytes) -> bytes:
    completed = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0", "-f", "flac", "pipe:1"],
        input=wav,
        capture_output=True,
        timeout=30,
        check=True,
    )
    return completed.stdout


def encode_m4a(wav: bytes, tmp_path: Path) -> bytes:
    """An m4a the way real recorders make them: index (moov) at the END.

    The mp4 muxer needs a seekable output, so this must encode to a real
    file — which is exactly what gives it the trailing index that broke
    pipe-based decoding (the founder's Sound Recorder bug, M2 close)."""
    source = tmp_path / "source.wav"
    source.write_bytes(wav)
    target = tmp_path / "clip.m4a"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-c:a",
            "aac",
            str(target),
        ],
        capture_output=True,
        timeout=30,
        check=True,
    )
    return target.read_bytes()


class TestCanonicalization:
    def test_wav_normalizes_to_canonical(self) -> None:
        # 44.1 kHz stereo in -> 16 kHz mono out: normalization is real.
        output = make_pipeline().process(
            wav_bytes(duration_seconds=1.0, sample_rate_hz=44100, channels=2)
        )
        assert output.media_format is MediaFormat.WAV
        assert output.audio.sample_rate_hz == CANONICAL_SAMPLE_RATE_HZ
        assert output.audio.channels == 1
        assert abs(output.audio.duration_seconds - 1.0) < 0.05
        assert output.speech.has_speech is True

    def test_flac_converges_to_the_same_canonical_audio(self) -> None:
        wav = wav_bytes(duration_seconds=1.0)
        output_wav = make_pipeline().process(wav)
        output_flac = make_pipeline().process(encode_flac(wav))
        assert output_flac.media_format is MediaFormat.FLAC
        # FLAC is lossless: identical PCM after normalization.
        assert output_flac.audio.pcm == output_wav.audio.pcm

    def test_m4a_with_trailing_index_decodes(self, tmp_path: Path) -> None:
        # Regression: MP4-family files (voice memos, Sound Recorder) carry
        # their moov index at EOF; decoding must survive that.
        m4a = encode_m4a(wav_bytes(duration_seconds=1.0), tmp_path)
        output = make_pipeline().process(m4a)
        assert output.media_format is MediaFormat.MP4
        assert abs(output.audio.duration_seconds - 1.0) < 0.1  # aac may pad edges
        assert output.speech.has_speech is True

    def test_every_stage_reports_timing(self) -> None:
        output = make_pipeline().process(wav_bytes())
        assert tuple(output.timings_ms) == STAGES
        assert all(value >= 0 for value in output.timings_ms.values())


class TestFailurePhilosophy:
    def expect_invalid_input(self, pipeline: MediaPipeline, payload: bytes, match: str) -> None:
        with pytest.raises(RuntimeServiceError, match=match) as exc_info:
            pipeline.process(payload)
        assert exc_info.value.error_type is RuntimeErrorType.INVALID_INPUT
        assert exc_info.value.param == "file"

    def test_empty_payload(self) -> None:
        self.expect_invalid_input(make_pipeline(), b"", "empty")

    def test_oversized_payload(self) -> None:
        pipeline = make_pipeline(max_upload_bytes=1024)
        self.expect_invalid_input(pipeline, wav_bytes(duration_seconds=1.0), "limit")

    def test_overlong_audio(self) -> None:
        pipeline = make_pipeline(max_audio_seconds=0.5)
        self.expect_invalid_input(pipeline, wav_bytes(duration_seconds=2.0), "duration")

    def test_corrupted_container(self) -> None:
        corrupted = b"fLaC" + b"\xde\xad\xbe\xef" * 100
        self.expect_invalid_input(make_pipeline(), corrupted, "decoded")

    def test_unrecognized_format_never_reaches_ffmpeg(self) -> None:
        self.expect_invalid_input(make_pipeline(), b"\x00\x01\x02 not audio", "unrecognized")


class TestStartupVerification:
    def test_verify_passes_with_real_ffmpeg(self) -> None:
        make_pipeline().verify()

    def test_missing_binary_is_an_internal_deploy_failure(self) -> None:
        pipeline = MediaPipeline(
            FfmpegDecoder("definitely-not-ffmpeg-binary", 5.0),
            EnergyVad(),
            max_upload_bytes=1024,
            max_audio_seconds=10.0,
        )
        with pytest.raises(RuntimeServiceError) as exc_info:
            pipeline.verify()
        assert exc_info.value.error_type is RuntimeErrorType.INTERNAL
