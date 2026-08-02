"""Sandboxed ffmpeg decoding: one subprocess, fixed argv, hard timeout.

Sandbox posture: no shell, a constant argument vector, untrusted bytes
enter ONLY via stdin and leave only via stdout, wall-clock bounded, and
the binary's presence is verified at startup so a misconfigured deploy
fails before it serves. ffmpeg's stderr goes to logs for operators —
never onto the wire (the wire gets the taxonomy; the logs get the
forensics).
"""

import subprocess

import structlog

from intelliai_runtime_contract import RuntimeErrorType
from intelliai_stt_runtime.failures import RuntimeServiceError
from intelliai_stt_runtime.pipeline.audio import CANONICAL_SAMPLE_RATE_HZ

logger = structlog.get_logger(__name__)


class FfmpegDecoder:
    """Decode + normalize in one pass: any supported input -> canonical PCM."""

    def __init__(self, binary: str, timeout_seconds: float) -> None:
        self._binary = binary
        self._timeout = timeout_seconds

    def verify(self) -> None:
        """Startup check: a runtime without its decoder must not serve."""
        try:
            # Fixed argv, shell-free; probes our own configured binary.
            completed = subprocess.run(  # noqa: S603
                [self._binary, "-version"],
                capture_output=True,
                timeout=10,
                check=False,
            )
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeServiceError(
                RuntimeErrorType.INTERNAL,
                f"ffmpeg binary {self._binary!r} is not available",
            ) from exc
        if completed.returncode != 0:
            raise RuntimeServiceError(
                RuntimeErrorType.INTERNAL,
                f"ffmpeg binary {self._binary!r} failed its version probe",
            )
        first_line = completed.stdout.decode("utf-8", errors="replace").splitlines()[:1]
        logger.info("ffmpeg_verified", version=first_line[0] if first_line else "unknown")

    def decode_to_canonical(self, payload: bytes) -> bytes:
        """Untrusted container bytes in, canonical 16 kHz mono s16le PCM out."""
        argv = [
            self._binary,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            "pipe:0",  # untrusted bytes enter here, never via a path or shell
            "-vn",  # audio only
            "-ac",
            "1",
            "-ar",
            str(CANONICAL_SAMPLE_RATE_HZ),
            "-f",
            "s16le",
            "pipe:1",
        ]
        try:
            # Fixed argv, shell-free; payload rides stdin only.
            completed = subprocess.run(  # noqa: S603
                argv,
                input=payload,
                capture_output=True,
                timeout=self._timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeServiceError(
                RuntimeErrorType.INVALID_INPUT,
                f"audio could not be decoded within {self._timeout:.0f}s",
                param="file",
            ) from exc
        except (FileNotFoundError, OSError) as exc:
            raise RuntimeServiceError(
                RuntimeErrorType.INTERNAL,
                "audio decoder is unavailable",
            ) from exc
        if completed.returncode != 0 or not completed.stdout:
            stderr_tail = completed.stderr.decode("utf-8", errors="replace")[-500:]
            logger.info("decode_failed", ffmpeg_stderr=stderr_tail)
            raise RuntimeServiceError(
                RuntimeErrorType.INVALID_INPUT,
                "audio could not be decoded (corrupted file or unsupported codec)",
                param="file",
            )
        return completed.stdout
