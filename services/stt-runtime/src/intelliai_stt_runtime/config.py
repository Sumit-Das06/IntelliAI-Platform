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
    # M55: external-server mode for BATCH qwen serving — when set, the
    # engine sends decodes to this operator-managed llama-server (the
    # pinned GPU launcher) instead of spawning its own CPU child. Empty
    # (the default) keeps today's spawn-a-child behavior everywhere.
    qwen3_server_url: str = ""
    # KV-bounded context: the spike measured the default 32k allocation at
    # 8.2 GiB RSS vs 1.5 GiB at 4096 — configuration, not identity.
    qwen3_context_tokens: int = Field(default=4096, ge=1024)
    qwen3_request_timeout_seconds: float = Field(default=300.0, gt=0)
    # Total request ceiling — 600.0 since Milestone 19 Phase 18, raised
    # from 120 only after the full proof battery passed (the engine
    # chunks 120-600 s internally; ≤120 s stays the proven direct pass).
    # Beyond 600 the loud refusal remains: the M17 silent-truncation
    # incident is the failure this ceiling exists to prevent.
    qwen3_max_audio_seconds: float = Field(default=600.0, gt=0)
    # ── M19 hybrid long-audio shape ─────────────────────────────────────
    # Audio ≤ direct decodes in one proven pass; audio between direct and
    # the ceiling is chunked INSIDE the engine (windows + overlap, seam
    # snapped toward the quietest nearby moment; 0 disables snapping).
    qwen3_direct_audio_seconds: float = Field(default=120.0, gt=0)
    qwen3_chunk_window_seconds: float = Field(default=100.0, gt=0)
    qwen3_chunk_overlap_seconds: float = Field(default=5.0, ge=0)
    qwen3_chunk_snap_radius_seconds: float = Field(default=8.0, ge=0)

    # ── hindi punctuation stage (Milestone 30) ──────────────────────────
    # A post-STT text stage: predicts punctuation positions and copies the
    # original words verbatim (the word-copy contract, M29B/M29C). OFF by
    # default everywhere; production stays OFF until its own promotion
    # decision. The stage is FAIL-OPEN at request time — but an ENABLED
    # deployment with unseeded/mishashed artifacts refuses to start, the
    # same law as every other artifact.
    punctuation_enabled: bool = False
    # Route-resolved language tags the stage applies to (comma-separated).
    # Gating is by the REQUESTED language (the route the gateway resolved),
    # never by a client's "auto" — no language, no stage.
    punctuation_languages: str = "hi,hi-IN"
    # The stage's request-time safety net; measured 600 s-tier latency is
    # ~0.45 s on the dev box, so 3 s is generous without masking hangs.
    punctuation_timeout_ms: float = Field(default=3000.0, gt=0)

    # ── english punctuation stage (Milestone 50) ────────────────────────
    # The SAME laws as the Hindi stage, on a separate flag and a separate
    # artifact (punct-en-kredor@v1, INT8 ONNX): OFF by default everywhere;
    # fail-open at request time; an ENABLED deployment with an unseeded or
    # mishashed artifact refuses to start. English is deliberately NOT
    # merged into `punctuation_languages` — the two stages gate and ship
    # independently.
    punctuation_en_enabled: bool = False
    punctuation_en_languages: str = "en,en-US,en-IN"
    # Measured M50 latency: a ~10-minute transcript punctuates in ~0.65 s
    # on the dev box, so 3 s is generous without masking hangs.
    punctuation_en_timeout_ms: float = Field(default=3000.0, gt=0)

    # ── realtime streaming sessions (Milestone 53) ──────────────────────
    # The M52/M52H architecture behind a flag that is OFF by default
    # everywhere; production stays OFF until its own promotion decision.
    # The public boundary is the GATEWAY (it authenticates before opening
    # a runtime session); this service's WS endpoint carries the same
    # internal posture as /v1/transcribe.
    realtime_enabled: bool = False
    realtime_languages: str = "en,en-US,en-IN,hi,hi-IN"
    # English partials run on a DEDICATED faster-whisper instance so a
    # realtime session never queues behind batch inference. Device is
    # deployment configuration (M52: cpu ≈1.5 s cadence; cuda passes
    # every proposed gate). Empty compute_type → int8 on cpu, float16
    # on cuda.
    realtime_whisper_device: str = "cpu"
    realtime_whisper_compute_type: str = ""
    # Hindi realtime decodes go to an OpenAI-compatible llama-server URL
    # (the M52H-verified CUDA build hosting the UNCHANGED E3 GGUF).
    # Empty → Hindi realtime unavailable on this deployment (clean
    # refusal); an ENABLED deployment with an unreachable URL refuses to
    # start — the artifact-seeding law applied to a network backend.
    realtime_qwen_url: str = ""
    # Session policy, all M52/M52H-measured defaults.
    realtime_min_step_seconds: float = Field(default=0.5, gt=0)
    # M54: the first decode may run earlier than the steady-state step —
    # first-partial time is perceived responsiveness.
    realtime_first_step_seconds: float = Field(default=0.3, gt=0)
    realtime_max_window_seconds: float = Field(default=25.0, gt=0)
    realtime_commit_margin_seconds: float = Field(default=5.0, gt=0)
    realtime_max_buffer_seconds: float = Field(default=60.0, gt=0)
    realtime_max_session_seconds: float = Field(default=900.0, gt=0)
    # M54: reuse the last hot decode as the final when only silence
    # follows it (measured finalization fast path). Own flag so the
    # behavior is rollback-able independently of the feature.
    realtime_final_fast_path: bool = True

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
