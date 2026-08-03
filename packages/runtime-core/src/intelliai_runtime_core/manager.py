"""ModelManager: the artifact manager — from bytes on a CDN to a warm engine.

Per slot, startup is a measured four-phase sequence:

    ensure (download + SHA-256 verify + cache)  ->  load (engine binding)
        ->  warm-up (first inference paid here, never by a customer)
        ->  serve (reused by every request until shutdown)

Engines are loaded once, reused across every request, unloaded once. No
request constructs or destroys an engine. Load and warm-up durations are
recorded per model and exposed operationally (/info) — startup cost is a
measured fact, not a feeling.

Lifecycle, never inference (ADR-0019): the manager is generic over the
runtime's engine type and never knows what an engine does. Its only
structural requirement is ``close()`` (shutdown is lifecycle), and warm-up
is a capability-defined deterministic probe injected by the runtime — the
manager guarantees the probe runs once per engine before serving; the
runtime decides what probing means for its capability.
"""

import asyncio
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import structlog

from intelliai_runtime_contract import RuntimeErrorType
from intelliai_runtime_core.failures import RuntimeServiceError
from intelliai_runtime_core.store import ArtifactSpec, ArtifactStore

logger = structlog.get_logger(__name__)

DEFAULT_SLOT = "default"


class SupportsClose(Protocol):
    """The manager's ONLY engine requirement: lifecycle can release it."""

    def close(self) -> None: ...


@dataclass(frozen=True)
class SlotSpec[EngineT: SupportsClose]:
    """One slot's configuration: artifact identity, files, and engine binding.

    ``load`` is a callable so the manager never imports an engine library —
    the import happens inside the engines/ module the callable comes from.
    It receives the verified local artifact directory (None for weight-free
    engines like a runtime's reference engine).
    """

    slot: str  # "default" | "premium" | "experimental"
    artifact: str  # registry artifact identifier this slot serves
    load: Callable[[Path | None], EngineT]
    files: ArtifactSpec | None = None  # None = nothing to download or verify


@dataclass(frozen=True)
class LoadedModel[EngineT: SupportsClose]:
    """A living engine, its artifact identity, and its measured startup cost."""

    slot: str
    artifact: str
    engine: EngineT
    load_ms: float
    warmup_ms: float


class ModelManager[EngineT: SupportsClose]:
    """Owns engine instances — and everything before them — for the process."""

    def __init__(
        self,
        slots: Sequence[SlotSpec[EngineT]],
        store: ArtifactStore | None = None,
        *,
        warm_up: Callable[[EngineT], None],
    ) -> None:
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
        if store is None and any(spec.files is not None for spec in slots):
            msg = "slots with artifact files require an ArtifactStore"
            raise ValueError(msg)
        self._specs = tuple(slots)
        self._store = store
        self._warm_up = warm_up
        self._by_artifact: dict[str, LoadedModel[EngineT]] = {}
        self._by_slot: dict[str, LoadedModel[EngineT]] = {}
        self._started = False

    @property
    def started(self) -> bool:
        return self._started

    async def startup(self) -> None:
        """Ensure -> load -> warm every slot, off the event loop, measured."""
        for spec in self._specs:
            local_dir: Path | None = None
            if spec.files is not None:
                assert self._store is not None  # noqa: S101 — enforced in __init__
                local_dir = await asyncio.to_thread(self._store.ensure, spec.files)

            load_started = time.perf_counter()
            engine = await asyncio.to_thread(spec.load, local_dir)
            load_ms = (time.perf_counter() - load_started) * 1000.0

            warm_started = time.perf_counter()
            await asyncio.to_thread(self._warm_up, engine)
            warmup_ms = (time.perf_counter() - warm_started) * 1000.0

            loaded = LoadedModel(
                slot=spec.slot,
                artifact=spec.artifact,
                engine=engine,
                load_ms=load_ms,
                warmup_ms=warmup_ms,
            )
            self._by_artifact[spec.artifact] = loaded
            self._by_slot[spec.slot] = loaded
            logger.info(
                "model_loaded",
                slot=spec.slot,
                artifact=spec.artifact,
                load_ms=round(load_ms, 1),
                warmup_ms=round(warmup_ms, 1),
            )
        self._started = True
        logger.info("runtime_ready", slots=len(self._specs))

    def lookup(self, artifact: str | None) -> LoadedModel[EngineT]:
        """The per-request question: which loaded engine serves this artifact?"""
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

    def loaded_models(self) -> tuple[LoadedModel[EngineT], ...]:
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
