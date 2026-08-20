"""The deployment's slot catalog: which artifacts this process hosts.

One capability service, plural deployments; each deployment declares the
artifacts it hosts, and each hosted artifact is a slot (ADR-0026). This
module is the whole of that declaration for synthesis — an engine
catalog, a parser for the ``INTELLIAI_TTS_SLOTS`` setting, and the
composition-time rules that make a misdeclared deployment fail at
startup instead of at request time.

Synthesis carries one thing transcription does not: **voices are
per-slot**. Each engine renders its own voice references, so each slot's
loader binds its engine to its voice map as the engine is constructed —
the only moment at which an engine instance and its bindings are both
in hand.

**What this module is not: routing.** It does not know languages, public
model identities, ladder statuses, or which artifact *should* serve
anything. The registry decides what serves a request; the runtime hosts
what it was told to host, and refuses anything else (ADR-0025).
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from intelliai_runtime_core import DEFAULT_SLOT, ArtifactSpec, SlotSpec
from intelliai_tts_runtime.config import Settings
from intelliai_tts_runtime.engines import SynthesisEngine, kokoro, reference
from intelliai_tts_runtime.engines.espeak_fallback import EspeakSubprocessFallback
from intelliai_tts_runtime.voices import KOKORO_VOICES, REFERENCE_VOICES, VoiceCatalog, VoiceMap

#: Separator between hosted-artifact declarations, and between an engine
#: and an explicit artifact identity within one declaration.
_SLOT_SEPARATOR: Final = ","
_ARTIFACT_SEPARATOR: Final = ":"


@dataclass(frozen=True)
class EngineBinding:
    """One engine this service knows how to host, and what it renders.

    ``weightless`` is a *fact*, not a permission: an engine with no
    downloaded weights has no artifact identity of its own, which is the
    only reason a deployment may host it under an arbitrary artifact id.
    An engine whose identity IS its weights can never be relabelled.
    """

    artifact: str
    voices: VoiceMap
    loader: Callable[[Path | None], SynthesisEngine]
    files: ArtifactSpec | None = None
    weightless: bool = False


#: Every engine this service can host. Adding an engine is one entry
#: here plus its adapter module — nothing else on the platform changes.
CATALOG: Final[dict[str, EngineBinding]] = {
    "reference": EngineBinding(
        artifact=reference.ARTIFACT_ID,
        voices=REFERENCE_VOICES,
        loader=lambda _dir: reference.load_reference_synthesis_engine(),
        weightless=True,
    ),
    "kokoro": EngineBinding(
        artifact=kokoro.ARTIFACT_ID,
        voices=KOKORO_VOICES,
        loader=kokoro.load_kokoro,
        files=kokoro.KOKORO_FILES,
    ),
}


def _declarations(declaration: str) -> tuple[tuple[str, str | None], ...]:
    """``"kokoro, reference:future-hi-v1"`` -> ((engine, artifact|None), ...)."""
    parsed: list[tuple[str, str | None]] = []
    for raw in declaration.split(_SLOT_SEPARATOR):
        item = raw.strip()
        if not item:
            continue
        engine, separator, artifact = item.partition(_ARTIFACT_SEPARATOR)
        parsed.append((engine.strip(), artifact.strip() if separator else None))
    if not parsed:
        msg = f"no artifacts declared: {declaration!r} names nothing to host"
        raise ValueError(msg)
    return tuple(parsed)


def _binding_loader(
    binding: EngineBinding, catalog: VoiceCatalog
) -> Callable[[Path | None], SynthesisEngine]:
    """Load the engine, then record which voices it renders."""

    def load(local_dir: Path | None) -> SynthesisEngine:
        engine = binding.loader(local_dir)
        catalog.bind(engine, binding.voices)
        return engine

    return load


def _kokoro_binding_for(settings: Settings) -> EngineBinding:
    """The kokoro binding, configured from the deployment's settings.

    The OOV fallback is constructed HERE — at composition time — so a
    deployment that declares ``oov_fallback=espeak`` with a missing or
    wrong-version binary refuses to START (the twice-learned lesson:
    absent configuration must fail loudly, never pass). The constructed
    fallback validates the pinned binary and its version in its own
    constructor; the engine only consumes the result.
    """
    base = CATALOG["kokoro"]
    if settings.oov_fallback != "espeak":
        return base
    fallback = EspeakSubprocessFallback(
        settings.espeak_binary,
        version_prefix=settings.espeak_version_pin,
        timeout_seconds=settings.espeak_timeout_seconds,
    )
    return EngineBinding(
        artifact=base.artifact,
        voices=base.voices,
        loader=lambda local_dir: kokoro.load_kokoro(local_dir, oov_fallback=fallback),
        files=base.files,
    )


def build_slot_specs(
    settings: Settings, catalog: VoiceCatalog
) -> tuple[SlotSpec[SynthesisEngine], ...]:
    """The deployment declaration, validated into slots.

    Slot names are lifecycle labels, never identity: ``default`` is the
    *role* of answering a request that pins no artifact, and the
    remaining slots are named for what they host. Identity is the
    artifact, which every request pins and the runtime matches exactly.
    """
    specs: list[SlotSpec[SynthesisEngine]] = []
    hosted: set[str] = set()
    for index, (engine, override) in enumerate(_declarations(settings.slots)):
        binding = _kokoro_binding_for(settings) if engine == "kokoro" else CATALOG.get(engine)
        if binding is None:
            msg = f"unknown engine {engine!r}; this service can host {sorted(CATALOG)}"
            raise ValueError(msg)
        artifact = binding.artifact
        if override is not None:
            if not binding.weightless:
                msg = (
                    f"engine {engine!r} carries weights, so its artifact identity is "
                    f"determined by them and cannot be declared as {override!r}"
                )
                raise ValueError(msg)
            if override == DEFAULT_SLOT:
                msg = f"{DEFAULT_SLOT!r} is a slot role, not an artifact identity"
                raise ValueError(msg)
            artifact = override
        if artifact in hosted:
            msg = f"artifact {artifact!r} declared twice; a deployment hosts each artifact once"
            raise ValueError(msg)
        hosted.add(artifact)
        specs.append(
            SlotSpec(
                slot=DEFAULT_SLOT if index == 0 else artifact,
                artifact=artifact,
                load=_binding_loader(binding, catalog),
                files=binding.files,
            )
        )
    return tuple(specs)
