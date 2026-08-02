"""Runtime settings — typed, frozen, fail-fast (the platform Settings pattern).

Concurrency knobs are the runtime's own business (ADR-0016: the runtime owns
its concurrency; the gateway owns routing and end-to-end deadlines). Slot
configuration becomes settings-driven when a second engine exists (M2 step 5);
until then the default slot is wired in ``main.build_manager``.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INTELLIAI_STT_", frozen=True, extra="ignore")

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    console_logs: bool = False  # pretty console rendering (dev); JSON otherwise

    # Inference slots actually executing at once (thread pool size)...
    max_concurrency: int = Field(default=2, ge=1)
    # ...plus how many admitted requests may wait for a slot. Beyond
    # concurrency + queue, the runtime answers `overloaded` immediately —
    # a fast honest no beats a slow timeout (the gateway owns retries).
    max_queue: int = Field(default=8, ge=0)

    # ── Media pipeline limits (failure philosophy in pipeline/pipeline.py) ──
    ffmpeg_path: str = "ffmpeg"
    decode_timeout_seconds: float = Field(default=30.0, gt=0)
    max_upload_bytes: int = Field(default=25 * 1024 * 1024, gt=0)
    max_audio_seconds: float = Field(default=600.0, gt=0)

    # ── Model serving ───────────────────────────────────────────────────
    # Which engine the default slot binds. "reference" needs no weights
    # (CI, tests); "whisper" requires the `whisper` extra and downloads
    # the hash-pinned artifact on first startup.
    default_engine: Literal["reference", "whisper"] = "reference"
    model_dir: Path = Path("models")  # ArtifactStore root (gitignored)
    # Precision is deployment configuration, never identity (ADR-0015).
    whisper_compute_type: str = "int8"
