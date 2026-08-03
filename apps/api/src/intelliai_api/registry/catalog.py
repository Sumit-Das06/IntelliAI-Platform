"""The catalog — the platform's served models, declared as reviewed code.

Every entry answers to the license gate: a commercial-use verdict verified
at the *served distribution* on a recorded date, per artifact version.
Changing what serves a public model is a diff to this file, reviewed like
any other code change, invisible to clients (ADR-0017).
"""

from datetime import date
from functools import lru_cache

from intelliai_api.registry.records import (
    ArtifactRecord,
    LicenseVerdict,
    PublicModelRecord,
    PublicVoiceRecord,
)
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
    ArtifactRecord(
        id="kokoro-82m",
        version=1,
        capability=Capability.SPEECH_SYNTHESIS,
        provenance=(
            "hexgrad/Kokoro-82M v1.0 (Apache-2.0): weights, config, and voice "
            "packs, all SHA-256-pinned from the Hugging Face distribution; "
            "served English-only, espeak-free (M3 design review §8). Training "
            "data includes synthetic audio from third-party models (provenance "
            "note, informational)."
        ),
        license=LicenseVerdict(
            license="Apache-2.0",
            commercial_use=True,
            verified_on=date(2026, 8, 3),
            source="https://huggingface.co/hexgrad/Kokoro-82M",
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
        released=date(2026, 8, 2),
    ),
    PublicModelRecord(
        id="intelliai-tts",
        capability=Capability.SPEECH_SYNTHESIS,
        service="tts-runtime",
        artifact_id="kokoro-82m",
        description="IntelliAI text-to-speech",
        released=date(2026, 8, 3),
    ),
)

# Public voice identities (placeholders pending the launch-naming
# decision; the ids are already permanent API surface for testers, so
# they follow every public-identity law from day one).
_VOICES = (
    PublicVoiceRecord(
        id="reference-alto",
        model="intelliai-tts",
        languages=("en",),
        description="Female English voice",
        released=date(2026, 8, 3),
    ),
    PublicVoiceRecord(
        id="reference-bass",
        model="intelliai-tts",
        languages=("en",),
        description="Male English voice",
        released=date(2026, 8, 3),
    ),
)


@lru_cache(maxsize=1)
def default_registry() -> Registry:
    """The validated platform registry; composition failures abort startup."""
    return Registry(artifacts=_ARTIFACTS, models=_MODELS, voices=_VOICES)
