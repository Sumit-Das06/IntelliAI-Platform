"""The metric registry — every metric's identity card, declared not inferred.

SPEECH_EVALUATION.md §3 made the rule; this module makes it mechanical:
a metric exists only as a registered `MetricSpec` carrying its layer,
direction, unit, confidence, and judge dependency. Dashboards, promotion
gates, and result records read these facts — they never guess. Reserved
(future) metrics are registered too: the architecture holds their place,
and a golden test pins the whole registry so any change is a conscious,
reviewed act.

**One registry, forever.** Recognition, generation and whatever comes
after share a single namespace. A per-capability registry would make a
name collision *undetectable* rather than merely awkward — two rulers
called ``rtf`` in two registries never meet, and the first reader to
average them finds out. Capability applicability is therefore a property
of a *spec* (:attr:`MetricSpec.capabilities`), never a separate namespace.

**Names are permanent.** A metric name, once recorded in the append-only
ledger, is quoted by evidence that outlives every process here. So a
changed ruler is a NEW metric name, never an edited one, and a wrong
metric is *withdrawn* rather than deleted — see :class:`MetricStatus`.

**Recordability is a write-time question, deliberately.** The read path
must stay permissive forever: the validators that guard record schemas
are pydantic field validators, which run on `model_validate` — i.e. on
every read of every committed record. A registry that refused withdrawn
names on read would make the ledger unparseable the first time we
corrected a mistake, which is precisely backwards. Writers call
:meth:`MetricRegistry.assert_recordable`; readers ask only whether the
name is known.
"""

from __future__ import annotations

from collections.abc import Iterator
from enum import StrEnum, unique
from typing import Final

from pydantic import BaseModel, ConfigDict, Field

from intelliai_runtime_contract import Capability

#: Bumped whenever the registered set or any spec's identity changes. It
#: is a *conscious-change* device, not an integrity proof: the golden test
#: pins this number and the full contents together, so a vocabulary edit
#: cannot be made without reading both. Nothing here can force the bump —
#: that would need a stored snapshot, which is not what this milestone is.
#:
#: v1 (B1) — the framework, with the 16 generation metrics migrated
#: v2 (B2) — the recognition accuracy family (methodology §3.1)
METRIC_REGISTRY_VERSION: Final = 2


@unique
class MetricLayer(StrEnum):
    CORRECTNESS = "correctness"  # did it produce the requested speech?
    PERFORMANCE = "performance"  # fast and cheap enough to serve?
    QUALITY = "quality"  # did it sound like high-quality speech?


@unique
class MetricDirection(StrEnum):
    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"


@unique
class MetricConfidence(StrEnum):
    """How much a number under this name can be trusted, and by what means."""

    HIGH = "high"  # objective, deterministic
    MEDIUM = "medium"  # objective but approximate (heuristics, judge-dependent)
    HUMAN = "human"  # structured subjective judgment
    RESERVED = "reserved"  # future capability; place held, nothing implemented


#: The confidence classes that describe a *measurement*. Human judgment
#: and reserved placeholders are deliberately excluded: the record schema
#: keeps measured and human evidence in separate fields, and this is the
#: fact that separation is computed from rather than restated.
MEASURED_CONFIDENCES: Final = (MetricConfidence.HIGH, MetricConfidence.MEDIUM)


@unique
class MetricStatus(StrEnum):
    """Whether this name may still be *written*. Orthogonal to confidence.

    Confidence answers "is there an implementation?"; status answers "is
    this still the right ruler?". They are kept apart because collapsing
    them loses the distinction between a metric awaiting implementation
    and one we got wrong — and a future engineer, seeing one field, could
    reasonably promote the second kind into service.

    There is deliberately no ``RESERVED`` member here: that meaning
    already belongs to :attr:`MetricConfidence.RESERVED`, and one meaning
    expressed by two fields is how a forbidden name gets activated in
    good faith.
    """

    ACTIVE = "active"
    #: Superseded or mistaken. Unwritable, and **still registered** — the
    #: records that already cite it must keep loading, forever. Deleting
    #: the name instead would make the append-only ledger unreadable at
    #: exactly the moment we admitted a mistake.
    WITHDRAWN = "withdrawn"


class MetricSpec(BaseModel):
    """One metric's permanent identity."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    layer: MetricLayer
    direction: MetricDirection
    unit: str = Field(min_length=1)
    confidence: MetricConfidence
    judge: str | None = None  # capability that judges it (e.g. "transcription")
    description: str = Field(min_length=1)
    status: MetricStatus = MetricStatus.ACTIVE
    #: The name that replaced this one. Set only alongside WITHDRAWN, so a
    #: reader meeting an old number in an old record can find the ruler it
    #: should be read against today.
    superseded_by: str | None = None
    #: Where this metric may be recorded. Empty means capability-generic —
    #: resource metrics measure a process, not a modality. A non-empty
    #: tuple is checked at write time only.
    capabilities: tuple[Capability, ...] = ()

    @property
    def recordable(self) -> bool:
        """Whether a runner may write a number under this name today."""
        return (
            self.status is MetricStatus.ACTIVE and self.confidence is not MetricConfidence.RESERVED
        )

    def applies_to(self, capability: Capability) -> bool:
        return not self.capabilities or capability in self.capabilities


class MetricNotRegisteredError(LookupError):
    """A name that no spec claims. Free-form identifiers never enter the ledger."""


class MetricNotRecordableError(ValueError):
    """The name is registered, but nothing may be written under it now."""


class DuplicateMetricError(ValueError):
    """Two specs claim one name — caught at registration, not at review."""


class MetricRegistry:
    """The single namespace of metric identities.

    Registration is explicit and ordered rather than a dict comprehension,
    because a comprehension keyed on ``spec.name`` resolves a duplicate
    *silently* — by whichever spec happens to come last — and discards the
    loser before any assertion could observe the collision. Since names are
    permanent and renaming is forbidden, a silent collision is not a bug
    that can be fixed later; it is a synonym pair that lives forever.
    """

    def __init__(self, version: int) -> None:
        self._version = version
        self._specs: dict[str, MetricSpec] = {}

    @property
    def version(self) -> int:
        return self._version

    def register(self, spec: MetricSpec) -> MetricSpec:
        """Add a spec, refusing a name already claimed."""
        existing = self._specs.get(spec.name)
        if existing is not None:
            raise DuplicateMetricError(
                f"metric {spec.name!r} is already registered as {existing.layer}/"
                f"{existing.unit}; names are permanent and may not be reused. A "
                "different computation or a different ruler is a different NAME."
            )
        if spec.superseded_by is not None and spec.status is not MetricStatus.WITHDRAWN:
            raise ValueError(
                f"metric {spec.name!r} names a successor while still {spec.status}; "
                "supersession is what withdrawal means, not an annotation on a live metric"
            )
        self._specs[spec.name] = spec
        return spec

    # ── Read path: permissive by design ─────────────────────────────
    #
    # Everything below is safe to call while loading a five-year-old
    # record. None of it consults `status`.

    def get(self, name: str) -> MetricSpec | None:
        return self._specs.get(name)

    def require(self, name: str) -> MetricSpec:
        """The spec for a name, or a refusal naming what the registry holds."""
        spec = self._specs.get(name)
        if spec is None:
            raise MetricNotRegisteredError(
                f"unknown metric {name!r}: metric names must exist in the registry"
            )
        return spec

    def __contains__(self, name: object) -> bool:
        return name in self._specs

    def __iter__(self) -> Iterator[MetricSpec]:
        return iter(self._specs.values())

    def __len__(self) -> int:
        return len(self._specs)

    def names(self) -> tuple[str, ...]:
        return tuple(self._specs)

    def of_layer(self, layer: MetricLayer) -> tuple[MetricSpec, ...]:
        return tuple(spec for spec in self._specs.values() if spec.layer is layer)

    # ── Write path: the only place recordability is enforced ────────

    def assert_recordable(self, name: str, *, capability: Capability | None = None) -> MetricSpec:
        """Refuse to let a runner write a number that cannot mean anything.

        Raises rather than returning a verdict: a boolean invites a caller
        to skip quietly, and a metric that silently stops being recorded
        looks exactly like a metric that was never measured.
        """
        spec = self.require(name)
        if spec.status is MetricStatus.WITHDRAWN:
            successor = f"; use {spec.superseded_by!r} instead" if spec.superseded_by else ""
            raise MetricNotRecordableError(
                f"metric {name!r} is withdrawn and may not be recorded{successor}. "
                "Records that already cite it remain readable."
            )
        if spec.confidence is MetricConfidence.RESERVED:
            raise MetricNotRecordableError(
                f"metric {name!r} is RESERVED: the architecture holds its place, "
                "but nothing implements it, so any number written under it would "
                "be a claim rather than a measurement"
            )
        if capability is not None and not spec.applies_to(capability):
            declared = ", ".join(c.value for c in spec.capabilities)
            raise MetricNotRecordableError(
                f"metric {name!r} applies to {declared}, not to {capability.value}"
            )
        return spec


def _build_registry() -> MetricRegistry:
    """Every metric the platform knows, registered one at a time.

    The order below is the reporting order of SPEECH_EVALUATION.md §3.
    """
    registry = MetricRegistry(METRIC_REGISTRY_VERSION)
    lower = MetricDirection.LOWER_IS_BETTER
    higher = MetricDirection.HIGHER_IS_BETTER
    synthesis = (Capability.SPEECH_SYNTHESIS,)
    recognition = (Capability.TRANSCRIPTION,)

    for spec in (
        # ── Recognition accuracy (B2) ───────────────────────────────────
        #
        # One aligner, several rulers. `wer_ascii` names its ruler because
        # it must stay self-identifying in records written before profiles
        # existed; the others name their COMPUTATION and are always read
        # together with the NormalizationProfile the record cites. That
        # asymmetry is deliberate and is the corrected form of methodology
        # A-1: the name cannot make cross-ruler averaging a type error
        # once one computation has several rulers, so the profile carries
        # the ruler and gates comparability.
        MetricSpec(
            name="wer_ascii",
            layer=MetricLayer.CORRECTNESS,
            direction=lower,
            unit="ratio",
            confidence=MetricConfidence.HIGH,
            description=(
                "Word error rate under ascii_en@v1, the frozen English ruler. "
                "The legacy compatibility anchor: preserves continuity with the "
                "2026-08-03 English baseline."
            ),
            capabilities=recognition,
        ),
        MetricSpec(
            name="wer_unicode",
            layer=MetricLayer.CORRECTNESS,
            direction=lower,
            unit="ratio",
            confidence=MetricConfidence.HIGH,
            description=(
                "Word error rate over a NormalizationProfile's word tokens. "
                "Uninterpretable without the profile the record cites."
            ),
            capabilities=recognition,
        ),
        MetricSpec(
            name="cer_unicode",
            layer=MetricLayer.CORRECTNESS,
            direction=lower,
            unit="ratio",
            confidence=MetricConfidence.HIGH,
            description=(
                "Character error rate over the same profile's character sequence, "
                "inter-word space retained. Primary where errors are sub-word."
            ),
            capabilities=recognition,
        ),
        # Rates share WER's denominator, which is what makes them exactly
        # additive with it. MEDIUM rather than HIGH because the split
        # between substitution and insertion+deletion is a property of the
        # frozen tie-break, not a physical fact: the total is robust, the
        # partition is a convention.
        MetricSpec(
            name="substitution_rate",
            layer=MetricLayer.CORRECTNESS,
            direction=lower,
            unit="ratio",
            confidence=MetricConfidence.MEDIUM,
            description="Substitutions over reference words, under the cited profile.",
            capabilities=recognition,
        ),
        MetricSpec(
            name="insertion_rate",
            layer=MetricLayer.CORRECTNESS,
            direction=lower,
            unit="ratio",
            confidence=MetricConfidence.MEDIUM,
            description="Insertions over reference words, under the cited profile.",
            capabilities=recognition,
        ),
        MetricSpec(
            name="deletion_rate",
            layer=MetricLayer.CORRECTNESS,
            direction=lower,
            unit="ratio",
            confidence=MetricConfidence.MEDIUM,
            description="Deletions over reference words, under the cited profile.",
            capabilities=recognition,
        ),
        MetricSpec(
            name="excess_word_ratio",
            layer=MetricLayer.CORRECTNESS,
            direction=lower,
            unit="ratio",
            confidence=MetricConfidence.MEDIUM,
            description=(
                "max(0, hypothesis - reference) / reference. A symptom of "
                "over-generation, never a proof of hallucination."
            ),
            capabilities=recognition,
        ),
        MetricSpec(
            name="hallucinated_words",
            layer=MetricLayer.CORRECTNESS,
            direction=lower,
            unit="count",
            confidence=MetricConfidence.HIGH,
            description=(
                "Words emitted where the CORPUS MANIFEST declares an empty "
                "reference. Never where a reference merely normalised to empty: "
                "that is a ruler failure and produces a Determination."
            ),
            capabilities=recognition,
        ),
        # ── Correctness (automated) ─────────────────────────────────────
        MetricSpec(
            name="round_trip_wer",
            layer=MetricLayer.CORRECTNESS,
            direction=lower,
            unit="ratio",
            confidence=MetricConfidence.MEDIUM,
            judge="transcription",
            description="WER of the judge STT's transcript against the input text.",
            capabilities=synthesis,
        ),
        MetricSpec(
            name="pronunciation_accuracy",
            layer=MetricLayer.CORRECTNESS,
            direction=higher,
            unit="ratio",
            confidence=MetricConfidence.MEDIUM,
            judge="transcription",
            description="Fraction of trap words surviving the round trip.",
            capabilities=synthesis,
        ),
        MetricSpec(
            name="clipping_ratio",
            layer=MetricLayer.CORRECTNESS,
            direction=lower,
            unit="ratio",
            confidence=MetricConfidence.HIGH,
            description="Samples at digital full scale over total samples.",
            capabilities=synthesis,
        ),
        MetricSpec(
            name="silence_ratio",
            layer=MetricLayer.CORRECTNESS,
            direction=lower,
            unit="ratio",
            confidence=MetricConfidence.MEDIUM,
            description="Low-energy frames over total frames (threshold heuristic).",
            capabilities=synthesis,
        ),
        MetricSpec(
            name="duration_plausibility",
            layer=MetricLayer.CORRECTNESS,
            direction=higher,
            unit="score",
            confidence=MetricConfidence.MEDIUM,
            description="1.0 when speaking rate falls in a plausible band, else 0.0.",
            capabilities=synthesis,
        ),
        # ── Performance (automated; measured by the runner/bench) ───────
        MetricSpec(
            name="time_to_first_audio_ms",
            layer=MetricLayer.PERFORMANCE,
            direction=lower,
            unit="ms",
            confidence=MetricConfidence.HIGH,
            description="Request start to first audio byte on the serving path.",
            capabilities=synthesis,
        ),
        MetricSpec(
            name="synthesis_latency_ms",
            layer=MetricLayer.PERFORMANCE,
            direction=lower,
            unit="ms",
            confidence=MetricConfidence.HIGH,
            description="Total synthesis request wall time.",
            capabilities=synthesis,
        ),
        MetricSpec(
            name="rtf",
            layer=MetricLayer.PERFORMANCE,
            direction=lower,
            unit="ratio",
            confidence=MetricConfidence.HIGH,
            description="Synthesis time over produced audio duration.",
            capabilities=synthesis,
        ),
        # Resource metrics measure a process, not a modality: they carry no
        # capability and are reused unchanged by every future family.
        MetricSpec(
            name="peak_memory_mib",
            layer=MetricLayer.PERFORMANCE,
            direction=lower,
            unit="MiB",
            confidence=MetricConfidence.HIGH,
            description="Peak container memory during evaluation.",
        ),
        MetricSpec(
            name="cpu_percent_max",
            layer=MetricLayer.PERFORMANCE,
            direction=lower,
            unit="percent",
            confidence=MetricConfidence.MEDIUM,
            description="Max sampled container CPU (docker stats lag applies).",
        ),
        # ── Quality (human) ─────────────────────────────────────────────
        MetricSpec(
            name="listening_preference",
            layer=MetricLayer.QUALITY,
            direction=higher,
            unit="win_rate",
            confidence=MetricConfidence.HUMAN,
            description="Anchored A/B win rate from the listening protocol.",
            capabilities=synthesis,
        ),
        MetricSpec(
            name="listening_naturalness",
            layer=MetricLayer.QUALITY,
            direction=higher,
            unit="score_1_5",
            confidence=MetricConfidence.HUMAN,
            description="Naturalness on the fixed 1-5 sheet; n recorded.",
            capabilities=synthesis,
        ),
        # ── Reserved (architecture holds the slot; nothing implemented) ──
        MetricSpec(
            name="predicted_mos",
            layer=MetricLayer.QUALITY,
            direction=higher,
            unit="score_1_5",
            confidence=MetricConfidence.RESERVED,
            description="Model-based naturalness prediction (adoption-gated).",
            capabilities=synthesis,
        ),
        MetricSpec(
            name="speaker_similarity",
            layer=MetricLayer.QUALITY,
            direction=higher,
            unit="ratio",
            confidence=MetricConfidence.RESERVED,
            description="Cloned-voice similarity to reference (cloning capability).",
            capabilities=synthesis,
        ),
        MetricSpec(
            name="voice_consistency",
            layer=MetricLayer.QUALITY,
            direction=higher,
            unit="ratio",
            confidence=MetricConfidence.RESERVED,
            description="Voice identity stability across utterances.",
            capabilities=synthesis,
        ),
        MetricSpec(
            name="emotion_preservation",
            layer=MetricLayer.QUALITY,
            direction=higher,
            unit="ratio",
            confidence=MetricConfidence.RESERVED,
            description="Expressive/emotional fidelity (S2ST, expressive TTS).",
            capabilities=synthesis,
        ),
    ):
        registry.register(spec)
    return registry


#: The platform's metric namespace.
#:
#: The recognition **accuracy** family landed in B2 under founder ruling
#: D-1. The performance, latency, startup and resource families have not:
#: none of them is language-aware, several are unrecordable today (the
#: artifact store is untimed, no accelerator sampling exists, the runtime
#: contract has no streaming method), and `recognition_rtf` is gated on
#: `duration_bands@v1`. They land with the milestones that build the
#: fields to hold them, so that each name is right when it lands.
METRICS: Final = _build_registry()
