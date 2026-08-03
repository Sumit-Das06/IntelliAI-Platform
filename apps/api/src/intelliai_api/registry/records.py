"""Registry record types — facts, strictly validated.

Unlike contract models (tolerant readers, ADR-0016), catalog records use
``extra="forbid"``: nothing arrives over a wire here, so an unknown field
is always a typo in our own catalog, and a typo must fail the build, not
ship silently. Records state facts truthfully — an artifact with a
non-commercial license is a *valid record*; it is the Registry that
refuses to route to it (the license gate lives at composition, mirroring
Registry V2's record-plane/resolution-plane split).
"""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from intelliai_runtime_contract import Capability


class _Record(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class LicenseVerdict(_Record):
    """Commercial-use verdict for ONE artifact version — never inherited
    from a model family (licenses shift mid-family; Constitution/ADR-0005)."""

    license: str = Field(min_length=1)  # SPDX identifier, e.g. "MIT"
    commercial_use: bool
    verified_on: date
    source: str = Field(min_length=1)  # where the verdict was verified


class ArtifactRecord(_Record):
    """A concrete set of trained weights the platform can serve.

    Identity carries no precision/hardware/format — quantization and
    conversion are build concerns owned by the runtime's ModelManager
    (ADR-0015: "data makes artifacts; determinism makes builds").
    """

    id: str = Field(min_length=1)  # e.g. "whisper-small"
    version: int = Field(ge=1)
    capability: Capability
    provenance: str = Field(min_length=1)  # free text in V1; structured lineage in V2
    license: LicenseVerdict


class PublicModelRecord(_Record):
    """A model name customers see. Never an engine name, never an upstream
    name — the whole point is that what serves it can change underneath."""

    id: str = Field(min_length=1)  # e.g. "intelliai-stt"
    capability: Capability
    service: str = Field(min_length=1)  # capability-named runtime, e.g. "stt-runtime"
    artifact_id: str = Field(min_length=1)
    description: str = ""
    released: date  # public product fact (the /v1/models `created` source)


class PublicVoiceRecord(_Record):
    """A voice name customers see — the second public identity axis.

    Same law as public models: never an engine voice token, never an
    upstream name — the engine binding behind a voice id can change
    without the id changing (M3 design review §5). V1 keeps these
    code-declarative beside the model catalog; Registry V2 absorbs public
    voice resolution exactly as it absorbs model resolution (direction
    recorded at M3 step 4 close)."""

    id: str = Field(min_length=1)  # e.g. "reference-alto" (placeholder pending naming)
    model: str = Field(min_length=1)  # the public model that serves it
    languages: tuple[str, ...] = Field(min_length=1)
    description: str = ""
    released: date


class Resolution(_Record):
    """The registry's answer: everything routing needs, nothing more."""

    public_model_id: str
    capability: Capability
    service: str
    artifact: ArtifactRecord
