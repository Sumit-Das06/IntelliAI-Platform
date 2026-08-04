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
    LanguageEvidence,
    LanguageStatus,
    LicenseVerdict,
    PublicModelRecord,
    PublicVoiceRecord,
    RouteSelector,
    ServingRoute,
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

# ── The Core Speech Language Policy ladder (F-M5-1, F-M5-2) ────────────
#
# Every (public model, language) pair the platform has an opinion about,
# and the evidence behind it. The rungs are a lifecycle: a language enters
# at `available` and reaches `supported` only via completed benchmark,
# evaluation evidence, production baseline, and explicit founder approval
# (F-M5-1). Nothing skips it — a production baseline is unobtainable
# without having served, so the bar itself forbids the jump.
#
# Languages absent from this table have no route and therefore no
# promise: undeclared traffic rides the default route, which is honest
# about promising nothing. The ladder reflects measured product evidence,
# not engine capability — the incumbent claims ~100 languages; the
# product promises what it has measured.

#: English STT was promoted by F-M5-2 on the evidence that already
#: existed when the ladder was ratified. Citations are strings in V1.5,
#: exactly as dataset versions are; M5 step 4 gives baselines their
#: (artifact, build, language, corpus version) identity and makes them
#: resolvable. The STT citation is a record path rather than a christened
#: baseline name because the M2 quality run predates the naming
#: discipline — an asymmetry step 4 closes, recorded honestly meanwhile.
_STT_EN_EVIDENCE = LanguageEvidence(
    corpus="stt-eval-seed@v1",
    quality_baseline="stt/results/2026-08-02-whisper-small",
    production_benchmark="2026-08-03-whisper-small-cpu-baseline",
    approval="F-M5-2 — Core Speech Language Policy ladder",
    approved_on=date(2026, 8, 4),
)

_TTS_EN_EVIDENCE = LanguageEvidence(
    corpus="tts-eval-seed@v1",
    quality_baseline="2026-08-03-kokoro-82m-cpu-v1",
    production_benchmark="2026-08-03-kokoro-82m-cpu-baseline",
    approval="F-M5-2 — Core Speech Language Policy ladder",
    approved_on=date(2026, 8, 4),
)

#: The serving-path verdict for whisper-small. End-to-end acoustic model:
#: no G2P, no lexicon, no per-language component — the same verdict
#: covers every language it serves. Recorded per route anyway, because
#: the next engine will not be like this one (the Hindi TTS gate was a
#: GPL phonemizer, not a model).
_WHISPER_SERVING_PATH = LicenseVerdict(
    license="MIT",
    commercial_use=True,
    verified_on=date(2026, 7, 31),
    source="https://huggingface.co/Systran/faster-whisper-small",
    covers="weights and CTranslate2 conversion; end-to-end model, no language-specific component",
)

_KOKORO_SERVING_PATH = LicenseVerdict(
    license="Apache-2.0",
    commercial_use=True,
    verified_on=date(2026, 8, 3),
    source="https://huggingface.co/hexgrad/Kokoro-82M",
    covers=(
        "weights, config, and English voice packs; espeak-free English path (M3 design review §8)"
    ),
)

_ROUTES = (
    ServingRoute(
        public_model_id="intelliai-stt",
        selector=RouteSelector(language="en"),
        status=LanguageStatus.SUPPORTED,
        artifact_id="whisper-small",
        license=_WHISPER_SERVING_PATH,
        evidence=_STT_EN_EVIDENCE,
    ),
    # Hindi and Arabic enter where every language enters (F-M5-1). The
    # incumbent already transcribes both; until M5 they did so unrouted,
    # unmeasured, and unlabelled. `available` is the honest name for what
    # was already happening — served, not promised.
    ServingRoute(
        public_model_id="intelliai-stt",
        selector=RouteSelector(language="hi"),
        status=LanguageStatus.AVAILABLE,
        artifact_id="whisper-small",
        license=_WHISPER_SERVING_PATH,
    ),
    ServingRoute(
        public_model_id="intelliai-stt",
        selector=RouteSelector(language="ar"),
        status=LanguageStatus.AVAILABLE,
        artifact_id="whisper-small",
        license=_WHISPER_SERVING_PATH,
    ),
    ServingRoute(
        public_model_id="intelliai-tts",
        selector=RouteSelector(language="en"),
        status=LanguageStatus.SUPPORTED,
        artifact_id="kokoro-82m",
        license=_KOKORO_SERVING_PATH,
        evidence=_TTS_EN_EVIDENCE,
    ),
    # Synthesis is not transcription: the incumbent has no licensed Hindi
    # or Arabic path at all, so the honest answer is refusal, not
    # best-effort. Each refusal is recorded as demand evidence.
    ServingRoute(
        public_model_id="intelliai-tts",
        selector=RouteSelector(language="hi"),
        status=LanguageStatus.UNAVAILABLE,
    ),
    ServingRoute(
        public_model_id="intelliai-tts",
        selector=RouteSelector(language="ar"),
        status=LanguageStatus.UNAVAILABLE,
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
    return Registry(artifacts=_ARTIFACTS, models=_MODELS, voices=_VOICES, routes=_ROUTES)
