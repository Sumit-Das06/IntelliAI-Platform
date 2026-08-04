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
from enum import StrEnum, unique

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    #: What the verdict spans. Empty on an artifact verdict (the weights
    #: are self-evidently the subject); load-bearing on a *route* verdict,
    #: where the subject is the whole language-specific serving path and a
    #: reviewer needs to know which components were actually examined.
    covers: str = ""


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


# ── Serving routes: the registry's second resolution input (ADR-0025) ───


@unique
class LanguageStatus(StrEnum):
    """The Language Support Ladder — what we tell a customer about one
    (public model, language) pair, and nothing else (ADR-0027).

    Exactly three stances toward a customer exist: we promise this, we
    serve it honestly without promising it, we do not serve it. The rungs
    are a *lifecycle*, not three independent labels (F-M5-1): a language
    enters at ``available`` and reaches ``supported`` only by producing
    evidence that ``available`` service makes possible. Nothing may skip
    it — enforced by the evidence bar, not by a state checker, because a
    production baseline is unobtainable without having served.

    Deliberately no ``experimental`` rung: internal experimentation is
    not a stance toward a customer and already has three homes (the
    artifact purpose flag, the usage-origin taxonomy, the reserved
    binding stages).
    """

    SUPPORTED = "supported"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


@unique
class RouteStage(StrEnum):
    """How much real traffic a binding carries — **reserved for Registry
    V2** (ADR-0027 decision 3).

    The vocabulary is named now so V2 inherits it rather than inventing
    it under pressure; the machine is inert. Any stage but ``production``
    is refused at record construction, exactly as the rating algorithm
    refuses an unsupported version rather than substituting one.
    """

    SHADOW = "shadow"
    CANARY = "canary"
    PRODUCTION = "production"


#: The only selector dimensions that have passed the Selector Admission
#: Test (ADR-0025 decision 3). Adding a member is a reviewed schema
#: change that must first answer: *could the customer know this value
#: from their own request or their own commercial agreement?* Dimensions
#: knowable only from our operations — hardware class, load, placement,
#: cost — are inadmissible and live on deployment records instead.
ADMITTED_SELECTOR_DIMENSIONS = frozenset({"language"})


def normalize_language(value: str | None) -> str | None:
    """Base subtag, lowercased: ``hi-IN`` routes as ``hi`` (ADR-0025).

    Applied to values arriving from *customers* — tolerant, because the
    wire is not ours. The full tag stays the recorded ledger fact; only
    routing is normalized. Catalog selectors are held to the stricter
    rule (already-normalized or the build fails), the same asymmetry as
    tolerant contract readers versus strict registry records.
    """
    if value is None:
        return None
    base = value.strip().replace("_", "-").split("-", 1)[0].lower()
    return base or None


class RouteSelector(_Record):
    """What a customer declared or contracted for — never what our
    infrastructure was doing.

    A typed record, not a match-dict: a stringly-typed policy engine is
    unvalidatable at composition time and every typo is a silent routing
    miss. Fields are **append-only**, the same discipline as contract
    models, and each new one must pass the Selector Admission Test
    recorded in :data:`ADMITTED_SELECTOR_DIMENSIONS`.

    An *empty* selector is not constructible here: the default route is
    ``PublicModelRecord.artifact_id``, and one fact must not have two
    representations.
    """

    language: str | None = None

    @model_validator(mode="after")
    def _selector_is_not_empty(self) -> "RouteSelector":
        if self.specificity == 0:
            msg = (
                "empty route selector: the default route is the public model's "
                "artifact_id, never a ServingRoute"
            )
            raise ValueError(msg)
        if self.language is not None and self.language != normalize_language(self.language):
            msg = (
                f"selector language {self.language!r} is not a normalized base subtag "
                f"(expected {normalize_language(self.language)!r}) — catalog records are strict"
            )
            raise ValueError(msg)
        return self

    @property
    def specificity(self) -> int:
        """How many dimensions this selector constrains (the Specificity
        Law's ordering); the default route's specificity is 0."""
        return sum(1 for name in ADMITTED_SELECTOR_DIMENSIONS if getattr(self, name) is not None)

    def matches(self, *, language: str | None) -> bool:
        """Whether a request with these declared values selects this route."""
        return self.language is None or self.language == language

    def can_both_match(self, other: "RouteSelector") -> bool:
        """Whether some single request could match both selectors.

        Two selectors that can both match *and* are equally specific are
        a composition-time error, never a runtime coin-flip. With one
        dimension this reduces to "identical selector"; it stays correct
        when dimensions are appended, which is why the general form is
        written now rather than a duplicate check.
        """
        return all(
            getattr(self, name) is None
            or getattr(other, name) is None
            or getattr(self, name) == getattr(other, name)
            for name in ADMITTED_SELECTOR_DIMENSIONS
        )


class LanguageEvidence(_Record):
    """The references that justify a ``supported`` rung (F-M5-1).

    One field per clause of the founder decision — completed benchmark,
    evaluation evidence, production baseline, explicit founder approval —
    expressed in the platform's existing evidence vocabulary, plus the
    corpus version that the Dataset Thread requires beneath any evidence.

    References are citation strings in V1.5, exactly as dataset versions
    are: M5 step 4 gives baselines their (artifact, build, language,
    corpus version) identity and makes these strings resolvable. What is
    structural *now* is that a promise cannot exist without them.
    """

    corpus: str = Field(min_length=1)  # versioned corpus, e.g. "stt-eval-seed@v1"
    quality_baseline: str = Field(min_length=1)  # the committed evaluation evidence
    production_benchmark: str = Field(min_length=1)  # the completed benchmark
    approval: str = Field(min_length=1)  # the founder decision that promoted it
    approved_on: date


class ServingRoute(_Record):
    """One selector bound to one artifact — binding, never coordination.

    **The Route/Strategy Boundary** (ADR-0025 decision 5). Coordination
    among routes — fallbacks, cascades, A/B splits, shadow or canary
    routing, ensembles, chained routing, regional failover — belongs to
    future *Serving Strategy* mechanisms and never changes the semantics
    of an individual route. The record stays intentionally small for the
    same reason ``runtime-core`` did: a bloated route record is never
    designed, it accretes one locally reasonable field at a time until
    resolution is no longer a pure function.

    ``license`` is the verdict for **this selector's whole serving
    path** — weights plus whatever the language additionally requires
    (voice packs, G2P, lexicons). The Hindi TTS gate was a GPL
    phonemizer, not a model; recording the verdict per route is that
    lesson made structural.
    """

    public_model_id: str = Field(min_length=1)
    selector: RouteSelector
    status: LanguageStatus
    artifact_id: str | None = None
    deployment: str | None = None  # defaults to the model's service (ADR-0026)
    license: LicenseVerdict | None = None  # the serving PATH, not just the weights
    evidence: LanguageEvidence | None = None
    stage: RouteStage = RouteStage.PRODUCTION

    @model_validator(mode="after")
    def _rung_obligations(self) -> "ServingRoute":
        if self.stage is not RouteStage.PRODUCTION:
            msg = (
                f"binding stage {self.stage.value!r} is reserved for Registry V2; "
                "M5 routes are fixed at 'production'"
            )
            raise ValueError(msg)
        bound = self.status is not LanguageStatus.UNAVAILABLE
        if bound and self.artifact_id is None:
            msg = (
                f"route {self.public_model_id!r}/{self.selector.language!r} is "
                f"{self.status.value} but binds no artifact"
            )
            raise ValueError(msg)
        if bound and self.license is None:
            msg = (
                f"route {self.public_model_id!r}/{self.selector.language!r} has no serving-path "
                "license verdict; a route's verdict must cover the language-specific path"
            )
            raise ValueError(msg)
        if not bound and (
            self.artifact_id is not None or self.license is not None or self.evidence is not None
        ):
            msg = (
                f"route {self.public_model_id!r}/{self.selector.language!r} is unavailable but "
                "carries a binding; a language we refuse to serve has nothing serving it"
            )
            raise ValueError(msg)
        if self.status is LanguageStatus.SUPPORTED and self.evidence is None:
            msg = (
                f"route {self.public_model_id!r}/{self.selector.language!r} claims 'supported' "
                "without evidence references (F-M5-1: benchmark, evaluation evidence, "
                "production baseline, founder approval)"
            )
            raise ValueError(msg)
        return self


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
    #: The artifact that renders this voice. A voice's sound *is* an
    #: artifact-specific asset (M3), so the voice is its own routing key
    #: — the registry owns WHICH artifact serves a voice, the runtime
    #: owns HOW it renders it. ``None`` means the model's default route,
    #: which is every voice today.
    artifact_id: str | None = None


class Resolution(_Record):
    """The registry's answer: everything routing needs, nothing more."""

    public_model_id: str
    capability: Capability
    service: str
    artifact: ArtifactRecord
    #: Which deployment of the capability service hosts the artifact
    #: (ADR-0026). Defaults to the service name, because today's topology
    #: is the degenerate case: one deployment per capability.
    deployment: str = ""

    @model_validator(mode="before")
    @classmethod
    def _deployment_defaults_to_service(cls, values: object) -> object:
        if isinstance(values, dict) and not values.get("deployment"):
            return {**values, "deployment": values.get("service")}
        return values
