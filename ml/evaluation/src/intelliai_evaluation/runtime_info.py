"""Reading a runtime's self-description.

The harness measures a service from another process and usually another
container, so the build, the decode configuration, the VAD owner and the
host are all invisible to it. The runtime reports them at ``/info``; this
module is the reader, and it exists so that no CLI flag ever duplicates a
fact the system already knows.

**Permissive by construction.** Unknown keys are ignored and every field
is optional. ``/info`` is expected to grow — a reader that refused an
unfamiliar key would make every future runtime addition a breaking change
for the harness, which is the opposite of what an additive endpoint is
for. What the harness does *not* find, it records as a Determination.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Reader(BaseModel):
    # `extra="ignore"` is the whole permissiveness policy, stated once.
    model_config = ConfigDict(frozen=True, extra="ignore")


class ModelInfo(_Reader):
    """One hosted artifact, as the runtime describes it.

    Per artifact rather than per process: a multi-slot deployment can host
    two artifacts under different builds, and a description covering both
    would describe neither.
    """

    slot: str
    artifact: str
    load_ms: float | None = None
    warmup_ms: float | None = None
    #: Absent on a runtime that predates self-description. The harness
    #: records a Determination rather than guessing a build.
    compute_type: str | None = None
    emitted_unit: str | None = None
    decode_params: dict[str, str] | None = None


class PoolInfo(_Reader):
    #: A live gauge, and the one documented exception to the endpoint's
    #: lifetime rule. Read here for completeness and never recorded as
    #: evidence: a number that moves between two calls is not identity.
    admitted: int | None = None
    max_concurrency: int | None = None
    max_queue: int | None = None


class RuntimeInfo(_Reader):
    """A runtime's operational identity and self-description."""

    service: str | None = None
    service_version: str | None = None
    contract_version: int | None = None
    capability: str | None = None
    vad_owner: str | None = None
    environment: dict[str, object] = Field(default_factory=dict)
    pool: PoolInfo = Field(default_factory=PoolInfo)
    models: tuple[ModelInfo, ...] = ()

    def hosted(self) -> set[str]:
        return {model.artifact for model in self.models}

    def model_for(self, artifact: str) -> ModelInfo | None:
        """The entry for one artifact, or None if this runtime does not host it."""
        for model in self.models:
            if model.artifact == artifact:
                return model
        return None
