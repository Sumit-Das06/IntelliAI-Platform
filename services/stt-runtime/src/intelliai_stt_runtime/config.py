"""Runtime settings — typed, frozen, fail-fast (the platform Settings pattern).

Concurrency knobs are the runtime's own business (ADR-0016: the runtime owns
its concurrency; the gateway owns routing and end-to-end deadlines). Slot
configuration is settings-driven: one deployment declares the artifacts it
hosts, and ``slots.build_slot_specs`` turns that declaration into slots.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
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
    # Which artifacts this deployment hosts, in declaration order: a
    # comma-separated list of engine names, each optionally followed by
    # `:artifact` to host a weightless engine under another identity
    # (how the reference engine simulates future artifacts). The FIRST
    # entry takes the `default` slot — the role that answers a request
    # pinning no artifact. "reference" needs no weights (CI, tests);
    # "whisper" requires the `whisper` extra and downloads the
    # hash-pinned artifact on first startup.
    #   "whisper"                      -> one deployment, one artifact
    #   "whisper,reference:future-hi"  -> two artifacts, one process
    slots: str = "reference"
    model_dir: Path = Path("models")  # ArtifactStore root (gitignored)
    # Precision is deployment configuration, never identity (ADR-0015).
    whisper_compute_type: str = "int8"

    # ── qwen3-asr research engine (Milestone 15E) ───────────────────────
    # The engine serves through a pinned llama.cpp llama-server child
    # process (the model has no CTranslate2 path). The binary is a local
    # research dependency, not an artifact: identity lives in the GGUF
    # pins, and the build is reported by the engine's description. The
    # default points at the 15B spike's pinned b10344 CPU build.
    qwen3_server_binary: Path = Path("weights/qwen3-asr-spike/llama-cpp/llama-server.exe")
    # KV-bounded context: the spike measured the default 32k allocation at
    # 8.2 GiB RSS vs 1.5 GiB at 4096 — configuration, not identity.
    qwen3_context_tokens: int = Field(default=4096, ge=1024)
    qwen3_request_timeout_seconds: float = Field(default=300.0, gt=0)

    # Replaced by `slots` in M5 step 2. Kept as a tripwire, not as a
    # feature: a stale INTELLIAI_STT_DEFAULT_ENGINE would otherwise be
    # ignored silently and a deployment meant to serve whisper would
    # come up serving the reference engine, healthy and wrong. The twice-
    # learned lesson: absent configuration must fail loudly, never pass.
    default_engine: Literal["reference", "whisper"] | None = None

    @model_validator(mode="after")
    def _refuse_the_replaced_setting(self) -> "Settings":
        if self.default_engine is not None:
            msg = (
                "INTELLIAI_STT_DEFAULT_ENGINE was replaced by INTELLIAI_STT_SLOTS "
                f"(use INTELLIAI_STT_SLOTS={self.default_engine!r}); a deployment now "
                "declares every artifact it hosts, not one engine"
            )
            raise ValueError(msg)
        return self
