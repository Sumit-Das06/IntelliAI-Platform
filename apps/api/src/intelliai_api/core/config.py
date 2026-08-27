"""Typed, environment-driven application settings.

Twelve-factor rules apply throughout:

- Environment variables are the only configuration channel. The ``.env`` file
  is a local-development convenience read from the working directory;
  production images contain no configuration files at all.
- Everything is validated once, at startup. A missing or malformed variable
  crashes the process with a precise error before it accepts traffic.
- Secrets are ``SecretStr``: they never appear in ``repr()``, logs, or
  tracebacks; code must explicitly call ``.get_secret_value()``.

Groups are separate ``BaseSettings`` classes, each with its own env prefix
(``INTELLIAI_DATABASE_URL``, ``INTELLIAI_STORAGE_ENDPOINT_URL`` …), composed
into one immutable ``Settings`` object.
"""

from enum import StrEnum
from functools import lru_cache
from typing import Final, Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_NAME = "intelliai-api"

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def _group(prefix: str) -> SettingsConfigDict:
    return SettingsConfigDict(
        env_prefix=prefix,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )


class Environment(StrEnum):
    DEV = "dev"
    TEST = "test"
    PROD = "prod"


class DatabaseSettings(BaseSettings):
    model_config = _group("INTELLIAI_DATABASE_")

    url: SecretStr  # postgresql+asyncpg://user:password@host:port/dbname
    # Raised from 5 at M4 step 3 (founder decision F8). A request holds
    # its pooled connection across the whole inference call, so
    # pool_size + overflow is a hard ceiling on in-flight requests —
    # measured at M4 step 2 as the binding constraint, capping inference
    # concurrency at 15 regardless of runtime capacity. Tuning the cheap
    # knob first, deliberately, rather than trading away the durability
    # guarantee that transaction ownership provides.
    pool_size: int = 20
    pool_max_overflow: int = 10
    echo: bool = False


class RedisSettings(BaseSettings):
    model_config = _group("INTELLIAI_REDIS_")

    url: SecretStr  # redis://[:password@]host:port/db


class AuthSettings(BaseSettings):
    model_config = _group("INTELLIAI_AUTH_")

    # Server-side pepper mixed into API-key hashes. A database dump alone is
    # useless without it. No default: the platform refuses to boot unpeppered.
    # Rotating it invalidates EVERY issued key (accepted M1 debt, ADR-0012).
    key_pepper: SecretStr


class StorageSettings(BaseSettings):
    model_config = _group("INTELLIAI_STORAGE_")

    endpoint_url: str  # any S3-compatible endpoint (dev: MinIO)
    access_key: str
    secret_key: SecretStr
    region: str = "us-east-1"
    audio_bucket: str = "intelliai-audio"


class CollectionSettings(BaseSettings):
    """Speech data collection — the flywheel's kill switch.

    ``enabled`` gates whether the app builds an object-storage client at
    all: off means no storage seam exists in the process and every
    collection path no-ops, regardless of tenant consent. An operational
    control, deliberately separate from consent (a legal fact about the
    tenant) — turning collection off platform-wide must never touch what
    anyone consented to. Settings are frozen at startup, so flipping it
    requires a restart.
    """

    model_config = _group("INTELLIAI_COLLECTION_")

    enabled: bool = True


#: Deployment names draw only from PERMANENT vocabulary — capabilities and
#: languages — and may never reference an engine (ADR-0026's naming law).
#: A language-named deployment is safe because languages are promises kept
#: regardless of what serves them; an engine-named one breaks precisely
#: when the engine changes, which is the moment nothing should have to.
#: This denylist grows with each adopted engine, exactly as the runtimes'
#: isolation denylist does.
ENGINE_VOCABULARY: Final = (
    "whisper",
    "kokoro",
    "ctranslate",
    "espeak",
    "hexgrad",
    "piper",
    "deepgram",
    "elevenlabs",
    "azure",
    "openai",
)


class RuntimeSettings(BaseSettings):
    """Where the inference runtimes live — deployment topology.

    One capability service is a *set of deployments* (ADR-0026). The two
    URLs below name the default deployment of each capability, which
    carries the service's own name — today's topology is the degenerate
    case of one deployment per capability. ``deployments`` adds the
    others, so growing a capability to several deployments is
    configuration rather than code.
    """

    model_config = _group("INTELLIAI_RUNTIMES_")

    stt_url: str = "http://localhost:8001"
    tts_url: str = "http://localhost:8002"
    #: Additional deployments as ``name=url`` pairs, comma-separated:
    #: ``"stt-runtime-indic=http://stt-indic:8001"``. Names must be
    #: resolvable by the registry's routes; a route naming a deployment
    #: this gateway has no URL for is an operations error, loudly.
    deployments: str = ""
    # The gateway's end-to-end patience with a runtime call (it owns the
    # deadline; the runtime owns per-stage limits — ADR-0016). Raised
    # 120 → 450 for M19 long-audio, sized to MEASUREMENT, not estimate:
    # the research probe suggested ~180 s for a 600 s chunked Hindi
    # decode, but the M19 engine-proof battery measured 297-340 s wall
    # on the same hardware — the deadline covers the worst measured run
    # with ~1.3x margin. Every OTHER layer already outlasts this (Caddy
    # sets no proxy timeout; uvicorn sets none; the engine bounds each
    # chunk itself; the admission lease sits above this deadline by its
    # own invariant). Configuration, not contract: the public API shape
    # is unchanged.
    timeout_seconds: float = 450.0

    #: Realtime STT sessions (Milestone 53): the runtime deployment that
    #: hosts them, as a WebSocket URL (``ws://…/v1/realtime``). Empty —
    #: the default everywhere — means realtime is OFF on this gateway:
    #: the public WS route refuses before accepting any audio. Production
    #: pins this empty until realtime's own promotion decision. The URL
    #: may name a deployment OUTSIDE the compose network (the staging GPU
    #: host) — that is deployment topology, exactly what this settings
    #: group exists to carry.
    stt_realtime_ws_url: str = ""

    #: Whether THIS deployment runs the speech-synthesis service and so
    #: must answer for it in readiness (M42). Default OFF because the
    #: base stack keeps TTS behind a compose profile: probing an absent
    #: service would report a permanent, meaningless DEGRADED and train
    #: operators to ignore the one signal that matters. A deployment
    #: that starts TTS — the production overlay and the production-shaped
    #: local stack — declares it here, so readiness is truthful in both
    #: directions: green only when everything the deployment serves is
    #: actually up.
    tts_enabled: bool = False

    def deployment_urls(self) -> dict[str, str]:
        """The deployment → URL map the gateway keys its clients by.

        Fail-fast, like every other setting: a malformed entry, a
        duplicate, or an engine-named deployment aborts startup rather
        than surfacing as a 500 on the one route that needed it.
        """
        urls = {"stt-runtime": self.stt_url, "tts-runtime": self.tts_url}
        for raw in self.deployments.split(","):
            entry = raw.strip()
            if not entry:
                continue
            name, separator, url = entry.partition("=")
            name, url = name.strip(), url.strip()
            if not (separator and name and url):
                msg = f"deployment entry {entry!r} is not 'name=url'"
                raise ValueError(msg)
            if not url.startswith(("http://", "https://")):
                msg = f"deployment {name!r} URL {url!r} is not an HTTP(S) URL"
                raise ValueError(msg)
            if name in urls:
                msg = f"deployment {name!r} declared twice"
                raise ValueError(msg)
            leaked = [word for word in ENGINE_VOCABULARY if word in name.lower()]
            if leaked:
                msg = (
                    f"deployment name {name!r} references an engine ({', '.join(leaked)}); "
                    "deployment names may use capabilities and languages only (ADR-0026)"
                )
                raise ValueError(msg)
            urls[name] = url
        return urls


class LimitsSettings(BaseSettings):
    """Admission control knobs (ADR-0022).

    ``socket_timeout_seconds`` is the one that matters: failing open is
    only survivable if it also fails *fast*. A limiter that blocks for
    the default connection timeout has taken the platform down more
    effectively than one that refuses requests.

    **Operational hazard, found by measurement at M4 step 3.** This
    budget interacts with hostname resolution. Point ``INTELLIAI_REDIS_URL``
    at an address, or at a name that resolves to the family the server
    actually listens on — a dual-stack name (``localhost`` → ``::1``
    first) in front of an IPv4-only Redis spends the whole budget on a
    failover, and the platform then runs unlimited while looking
    perfectly healthy. The alarm fires, which is the point of failing
    loudly; but the cause is configuration, not Redis.
    """

    model_config = _group("INTELLIAI_LIMITS_")

    enabled: bool = True
    # Key prefix for every bucket and lease. Lets several deployments (or
    # several test runs) share one Redis without silently sharing each
    # other's allowances — a shared bucket is an outage that looks like a
    # rate limit.
    namespace: str = ""
    socket_timeout_seconds: float = 0.25
    # Transport ceiling on any request body, enforced BEFORE the gateway
    # buffers an upload (ADR: 14A). Above the STT runtime's 25 MiB audio
    # cap by a deliberate margin — multipart framing costs bytes, and the
    # runtime's own validation must stay the message customers see for
    # oversized AUDIO; this ceiling only stops memory-pressure floods.
    max_request_bytes: int = 30 * 1024 * 1024
    # How long an in-flight slot is held if the process never releases it.
    # Generously above the gateway's own runtime deadline, so a slow
    # request is never evicted while it is still legitimately running.
    # Re-sized with the M19 deadline (450 s): a legitimate 600 s chunked
    # request measures up to ~340 s in flight, and the eviction insurance
    # must outlast the deadline or a healthy long request frees its slot
    # early (silent over-admission).
    lease_seconds: int = 540


class MeteringSettings(BaseSettings):
    """The ledger's degrade-loud path (ADR-0021).

    When the ledger refuses a write, the customer still receives their
    response — which is only defensible if the fact survives somewhere the
    database is not. ``fallback_path`` is that local sink; the CRITICAL
    log line is always emitted regardless. Set the path empty to rely on
    logs alone (correct where the filesystem is not durable anyway).
    """

    model_config = _group("INTELLIAI_METERING_")

    fallback_path: str = "usage-fallback.jsonl"


class Settings(BaseSettings):
    """Root settings object; one instance per application instance."""

    model_config = _group("INTELLIAI_")

    env: Environment = Environment.DEV
    log_level: LogLevel = "INFO"

    # ── Registry profile (Milestone 18) ────────────────────────────────
    # "production" composes the live catalog exactly as reviewed.
    # "staging" ADDITIONALLY activates the prepared-but-unpromoted
    # proposals (registry/proposals.py) for LOCAL/STAGING verification —
    # the only sanctioned way to route a request to a research candidate
    # through the real gateway. Guard tests pin: the default is
    # production, and no committed compose file ever sets this variable.
    registry_profile: Literal["production", "staging"] = "production"

    @model_validator(mode="after")
    def _staging_never_reaches_prod(self) -> "Settings":
        if self.registry_profile == "staging" and self.env is Environment.PROD:
            msg = (
                "INTELLIAI_REGISTRY_PROFILE=staging is refused when INTELLIAI_ENV=prod: "
                "research candidates reach production only through the reviewed "
                "promotion commit (registry/proposals.py), never through configuration"
            )
            raise ValueError(msg)
        return self

    auth: AuthSettings = Field(default_factory=AuthSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    collection: CollectionSettings = Field(default_factory=CollectionSettings)
    runtimes: RuntimeSettings = Field(default_factory=RuntimeSettings)
    metering: MeteringSettings = Field(default_factory=MeteringSettings)
    limits: LimitsSettings = Field(default_factory=LimitsSettings)

    @property
    def is_dev(self) -> bool:
        return self.env is Environment.DEV

    @property
    def is_prod(self) -> bool:
        return self.env is Environment.PROD


@lru_cache
def get_settings() -> Settings:
    """Process-wide settings, built once on first use.

    Only entrypoints (server startup, scripts) call this. Application code
    receives settings through dependency injection — tests inject their own
    ``Settings`` via ``create_app(settings=...)`` and never touch this cache.
    """
    return Settings()
