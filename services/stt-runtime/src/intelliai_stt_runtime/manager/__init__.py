"""Model lifecycle — the ModelManager owns every engine instance.

Engines are loaded once at application startup, reused across every
request, and unloaded once at shutdown. No request ever constructs or
destroys an engine. Step 5 adds this module's remaining duties: artifact
download, checksum verification, cache, and warm-up.
"""

from intelliai_stt_runtime.manager.manager import LoadedModel, ModelManager, SlotSpec

__all__ = ["LoadedModel", "ModelManager", "SlotSpec"]
