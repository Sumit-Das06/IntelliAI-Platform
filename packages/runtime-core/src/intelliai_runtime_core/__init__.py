"""Shared lifecycle machinery for every IntelliAI runtime (ADR-0019).

runtime-core owns lifecycle, never inference: ensure -> load -> warm ->
ready -> execute -> shutdown. It has zero knowledge of what any model
does — engines are opaque type parameters whose only lifecycle requirement
is ``close()``, and warm-up is a capability-defined deterministic probe
injected by each runtime. The boundary test suite enforces this in CI.
"""

from intelliai_runtime_core.description import (
    EngineDescription,
    effective_parameters,
    host_environment,
    interpreter_identity,
    package_versions,
)
from intelliai_runtime_core.failures import RuntimeServiceError
from intelliai_runtime_core.logging import configure_logging
from intelliai_runtime_core.manager import (
    DEFAULT_SLOT,
    LoadedModel,
    ModelManager,
    SlotSpec,
    SupportsClose,
)
from intelliai_runtime_core.pool import WorkerPool
from intelliai_runtime_core.store import ArtifactFile, ArtifactSpec, ArtifactStore, sha256_file

__all__ = [
    "DEFAULT_SLOT",
    "ArtifactFile",
    "ArtifactSpec",
    "ArtifactStore",
    "EngineDescription",
    "LoadedModel",
    "ModelManager",
    "RuntimeServiceError",
    "SlotSpec",
    "SupportsClose",
    "WorkerPool",
    "configure_logging",
    "effective_parameters",
    "host_environment",
    "interpreter_identity",
    "package_versions",
    "sha256_file",
]
