"""The deployment's slot catalog: which artifacts this process hosts.

One capability service, plural deployments; each deployment declares the
artifacts it hosts, and each hosted artifact is a slot (ADR-0026). This
module is the whole of that declaration for transcription — an engine
catalog, a parser for the ``INTELLIAI_STT_SLOTS`` setting, and the
composition-time rules that make a misdeclared deployment fail at
startup instead of at request time.

**What this module is not: routing.** It does not know languages, public
model identities, ladder statuses, or which artifact *should* serve
anything. It turns a deployment declaration into ``SlotSpec``s and
stops. The registry decides what serves a request; the runtime hosts
what it was told to host, and refuses anything else (ADR-0025).
"""

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Final

from intelliai_runtime_core import DEFAULT_SLOT, ArtifactSpec, SlotSpec
from intelliai_stt_runtime.config import Settings
from intelliai_stt_runtime.engines import TranscriptionEngine, reference, whisper

#: Separator between hosted-artifact declarations, and between an engine
#: and an explicit artifact identity within one declaration.
_SLOT_SEPARATOR: Final = ","
_ARTIFACT_SEPARATOR: Final = ":"


@dataclass(frozen=True)
class EngineBinding:
    """One engine this service knows how to host, and what it costs to.

    ``weightless`` is a *fact*, not a permission: an engine with no
    downloaded weights has no artifact identity of its own, which is the
    only reason a deployment may host it under an arbitrary artifact id.
    An engine whose identity IS its weights can never be relabelled.
    """

    artifact: str
    loader: Callable[[Settings], Callable[[Path | None], TranscriptionEngine]]
    files: ArtifactSpec | None = None
    weightless: bool = False


def _load_reference(_: Settings) -> Callable[[Path | None], TranscriptionEngine]:
    return lambda _dir: reference.load_reference_engine()


def _load_whisper(settings: Settings) -> Callable[[Path | None], TranscriptionEngine]:
    return partial(whisper.load_faster_whisper, compute_type=settings.whisper_compute_type)


#: Every engine this service can host. Adding an engine is one entry
#: here plus its adapter module — nothing else on the platform changes.
CATALOG: Final[dict[str, EngineBinding]] = {
    "reference": EngineBinding(
        artifact=reference.ARTIFACT_ID,
        loader=_load_reference,
        weightless=True,
    ),
    "whisper": EngineBinding(
        artifact=whisper.ARTIFACT_ID,
        loader=_load_whisper,
        files=whisper.WHISPER_SMALL_FILES,
    ),
}


def _declarations(declaration: str) -> tuple[tuple[str, str | None], ...]:
    """``"whisper, reference:future-hi-v1"`` -> ((engine, artifact|None), ...)."""
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


def build_slot_specs(settings: Settings) -> tuple[SlotSpec[TranscriptionEngine], ...]:
    """The deployment declaration, validated into slots.

    Slot names are lifecycle labels, never identity: ``default`` is the
    *role* of answering a request that pins no artifact, and the
    remaining slots are named for what they host. Identity is the
    artifact, which every request pins and the runtime matches exactly.
    """
    specs: list[SlotSpec[TranscriptionEngine]] = []
    hosted: set[str] = set()
    for index, (engine, override) in enumerate(_declarations(settings.slots)):
        binding = CATALOG.get(engine)
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
                load=binding.loader(settings),
                files=binding.files,
            )
        )
    return tuple(specs)
