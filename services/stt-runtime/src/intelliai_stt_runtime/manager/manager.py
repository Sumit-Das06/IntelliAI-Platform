"""ModelManager: slots -> loaded engines, from startup to shutdown."""

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import structlog

from intelliai_runtime_contract import RuntimeErrorType
from intelliai_stt_runtime.engines import TranscriptionEngine
from intelliai_stt_runtime.failures import RuntimeServiceError

logger = structlog.get_logger(__name__)

DEFAULT_SLOT = "default"


@dataclass(frozen=True)
class SlotSpec:
    """One slot's configuration: which artifact, and how to load its engine.

    ``load`` is a callable so the manager never imports an engine library —
    the import happens inside the engines/ module the callable comes from,
    which is what keeps the isolation boundary honest. Loaders may block
    (model weights take seconds); the manager runs them off the event loop.
    Loaders return a WARM engine — first-token latency is paid at startup,
    never by the first customer request.
    """

    slot: str  # "default" | "premium" | "experimental"
    artifact: str  # registry artifact identifier this slot serves
    load: Callable[[], TranscriptionEngine]


@dataclass(frozen=True)
class LoadedModel:
    """A living engine paired with the artifact identity it serves."""

    slot: str
    artifact: str
    engine: TranscriptionEngine


class ModelManager:
    """Owns engine instances for the life of the process."""

    def __init__(self, slots: Sequence[SlotSpec]) -> None:
        if not slots:
            msg = "ModelManager requires at least one slot"
            raise ValueError(msg)
        slot_names = [spec.slot for spec in slots]
        if len(slot_names) != len(set(slot_names)):
            msg = "slot names must be unique"
            raise ValueError(msg)
        artifacts = [spec.artifact for spec in slots]
        if len(artifacts) != len(set(artifacts)):
            msg = "one loaded artifact per slot: artifacts must be unique"
            raise ValueError(msg)
        if DEFAULT_SLOT not in slot_names:
            msg = f"a {DEFAULT_SLOT!r} slot is required"
            raise ValueError(msg)
        self._specs = tuple(slots)
        self._by_artifact: dict[str, LoadedModel] = {}
        self._by_slot: dict[str, LoadedModel] = {}
        self._started = False

    @property
    def started(self) -> bool:
        return self._started

    async def startup(self) -> None:
        """Load every slot's engine (off the event loop), then open for business."""
        for spec in self._specs:
            engine = await asyncio.to_thread(spec.load)
            loaded = LoadedModel(slot=spec.slot, artifact=spec.artifact, engine=engine)
            self._by_artifact[spec.artifact] = loaded
            self._by_slot[spec.slot] = loaded
            logger.info("model_loaded", slot=spec.slot, artifact=spec.artifact)
        self._started = True
        logger.info("runtime_ready", slots=len(self._specs))

    def lookup(self, artifact: str | None) -> LoadedModel:
        """The per-request question: which loaded engine serves this artifact?

        Requests only ever *look up* engines — construction and destruction
        happen exclusively in startup/shutdown."""
        if not self._started:
            raise RuntimeServiceError(
                RuntimeErrorType.NOT_READY,
                "models are still loading; retry shortly",
            )
        if artifact is None:
            return self._by_slot[DEFAULT_SLOT]
        loaded = self._by_artifact.get(artifact)
        if loaded is None:
            raise RuntimeServiceError(
                RuntimeErrorType.INVALID_INPUT,
                f"artifact {artifact!r} is not served by this runtime",
                param="model",
            )
        return loaded

    def loaded_models(self) -> tuple[LoadedModel, ...]:
        """Operational introspection (the /info source)."""
        return tuple(self._by_slot.values())

    async def shutdown(self) -> None:
        """Release every engine exactly once."""
        for loaded in self._by_slot.values():
            await asyncio.to_thread(loaded.engine.close)
            logger.info("model_unloaded", slot=loaded.slot, artifact=loaded.artifact)
        self._by_artifact.clear()
        self._by_slot.clear()
        self._started = False
