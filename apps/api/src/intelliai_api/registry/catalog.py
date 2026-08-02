"""The catalog — the platform's served models, declared as reviewed code.

Every entry answers to the license gate: a commercial-use verdict verified
at the *served distribution* on a recorded date, per artifact version.
Changing what serves a public model is a diff to this file, reviewed like
any other code change, invisible to clients (ADR-0017).
"""

from datetime import date
from functools import lru_cache

from intelliai_api.registry.records import ArtifactRecord, LicenseVerdict, PublicModelRecord
from intelliai_api.registry.registry import Registry
from intelliai_runtime_contract import Capability

_ARTIFACTS = (
    ArtifactRecord(
        id="whisper-small",
        version=1,
        capability=Capability.TRANSCRIPTION,
        provenance=(
            "openai/whisper small (MIT); served via the Systran faster-whisper "
            "CTranslate2 conversion"
        ),
        license=LicenseVerdict(
            license="MIT",
            commercial_use=True,
            verified_on=date(2026, 7, 31),
            source="https://huggingface.co/Systran/faster-whisper-small",
        ),
    ),
)

_MODELS = (
    PublicModelRecord(
        id="intelliai-stt",
        capability=Capability.TRANSCRIPTION,
        service="stt-runtime",
        artifact_id="whisper-small",
        description="IntelliAI speech-to-text",
    ),
)


@lru_cache(maxsize=1)
def default_registry() -> Registry:
    """The validated platform registry; composition failures abort startup."""
    return Registry(artifacts=_ARTIFACTS, models=_MODELS)
