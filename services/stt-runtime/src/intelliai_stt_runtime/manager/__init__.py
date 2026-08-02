"""Model lifecycle — the ModelManager is the artifact manager.

Download, SHA-256 verification, cache, engine loading, warm-up, lifecycle,
and engine binding all live here. Engines are loaded once at startup,
reused across every request, unloaded once at shutdown. No request ever
constructs or destroys an engine; nothing is ever loaded unverified.
"""

from intelliai_stt_runtime.manager.manager import LoadedModel, ModelManager, SlotSpec
from intelliai_stt_runtime.manager.store import ArtifactFile, ArtifactSpec, ArtifactStore

__all__ = [
    "ArtifactFile",
    "ArtifactSpec",
    "ArtifactStore",
    "LoadedModel",
    "ModelManager",
    "SlotSpec",
]
