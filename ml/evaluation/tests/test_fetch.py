"""Synthesis must be deterministic; verification must be unforgiving.

No network in tests: URL clips are exercised only through hash/refusal
logic with local files.
"""

import wave
from pathlib import Path

import httpx
import pytest

from intelliai_evaluation.dataset import EvalClip, SyntheticSpec
from intelliai_evaluation.fetch import (
    ClipIntegrityError,
    generate_synthetic,
    materialize_clip,
    sha256_file,
)


class TestSyntheticGeneration:
    def test_silence_is_deterministic(self, tmp_path: Path) -> None:
        spec = SyntheticSpec(kind="silence", duration_seconds=2.0)
        first, second = tmp_path / "a.wav", tmp_path / "b.wav"
        generate_synthetic(spec, first)
        generate_synthetic(spec, second)
        assert sha256_file(first) == sha256_file(second)

    def test_tone_is_deterministic(self, tmp_path: Path) -> None:
        spec = SyntheticSpec(kind="tone", duration_seconds=1.0, frequency_hz=440.0)
        first, second = tmp_path / "a.wav", tmp_path / "b.wav"
        generate_synthetic(spec, first)
        generate_synthetic(spec, second)
        assert sha256_file(first) == sha256_file(second)

    def test_wav_properties_match_spec(self, tmp_path: Path) -> None:
        spec = SyntheticSpec(kind="silence", duration_seconds=3.0, sample_rate_hz=16000)
        target = tmp_path / "clip.wav"
        generate_synthetic(spec, target)
        with wave.open(str(target), "rb") as reader:
            assert reader.getnchannels() == 1
            assert reader.getsampwidth() == 2
            assert reader.getframerate() == 16000
            assert reader.getnframes() == 48000

    def test_silence_frames_are_zero(self, tmp_path: Path) -> None:
        target = tmp_path / "s.wav"
        generate_synthetic(SyntheticSpec(kind="silence", duration_seconds=0.5), target)
        with wave.open(str(target), "rb") as reader:
            assert reader.readframes(reader.getnframes()) == b"\x00" * (reader.getnframes() * 2)

    def test_tone_is_not_silence(self, tmp_path: Path) -> None:
        target = tmp_path / "t.wav"
        generate_synthetic(SyntheticSpec(kind="tone", duration_seconds=0.5), target)
        with wave.open(str(target), "rb") as reader:
            frames = reader.readframes(reader.getnframes())
        assert any(byte != 0 for byte in frames)


class TestPathMaterialization:
    """Path clips verify identity; they never create or download."""

    def _clip(self, path: str, sha256: str) -> EvalClip:
        return EvalClip(
            id="p",
            language="hi",
            reference_text="नमस्ते",
            duration_seconds=1.0,
            license="CC-BY-4.0",
            path=path,
            sha256=sha256,
        )

    def test_matching_pin_is_returned(self, tmp_path: Path) -> None:
        audio = tmp_path / "hi" / "clip.wav"
        audio.parent.mkdir(parents=True)
        audio.write_bytes(b"pcm-bytes")
        clip = self._clip("hi/clip.wav", sha256_file(audio))
        with httpx.Client() as client:
            resolved = materialize_clip(clip, tmp_path, client)
        assert resolved == audio

    def test_missing_file_is_refused(self, tmp_path: Path) -> None:
        clip = self._clip("hi/absent.wav", "0" * 64)
        with httpx.Client() as client, pytest.raises(ClipIntegrityError, match="does not exist"):
            materialize_clip(clip, tmp_path, client)

    def test_mismatched_pin_is_refused(self, tmp_path: Path) -> None:
        audio = tmp_path / "clip.wav"
        audio.write_bytes(b"tampered")
        clip = self._clip("clip.wav", "0" * 64)
        with httpx.Client() as client, pytest.raises(ClipIntegrityError, match="SHA-256 mismatch"):
            materialize_clip(clip, tmp_path, client)

    def test_mismatched_local_file_is_not_deleted(self, tmp_path: Path) -> None:
        # A bad download is discarded; a bad LOCAL file is somebody's
        # data and materialization must not destroy it.
        audio = tmp_path / "clip.wav"
        audio.write_bytes(b"tampered")
        clip = self._clip("clip.wav", "0" * 64)
        with httpx.Client() as client, pytest.raises(ClipIntegrityError):
            materialize_clip(clip, tmp_path, client)
        assert audio.exists()


class TestHashing:
    def test_sha256_matches_hashlib(self, tmp_path: Path) -> None:
        import hashlib

        target = tmp_path / "f.bin"
        payload = b"intelliai" * 10_000  # spans multiple read chunks
        target.write_bytes(payload)
        assert sha256_file(target) == hashlib.sha256(payload).hexdigest()

    def test_sha256_is_stable(self, tmp_path: Path) -> None:
        a, b = tmp_path / "a.bin", tmp_path / "b.bin"
        a.write_bytes(b"same content")
        b.write_bytes(b"same content")
        assert sha256_file(a) == sha256_file(b)
        c = tmp_path / "c.bin"
        c.write_bytes(b"different content")
        assert sha256_file(c) != sha256_file(a)
