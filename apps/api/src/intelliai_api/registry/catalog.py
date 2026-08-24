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
    CorpusOwnership,
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
    # ── The M26 promotion: the approved Hindi specialist ────────────────
    # Identity pinned end to end; the promotion evidence chain is M23
    # (training + eight research gates) → M24 (promotion readiness vs the
    # incumbent through the real product path) → M25 (production-shaped
    # stack + real Web/Android verification). Identity re-verified by
    # research/experiments/24-e3-promotion/identity.json.
    ArtifactRecord(
        id="qwen3-asr-0.6b-hi-ft-e3",
        version=1,
        capability=Capability.TRANSCRIPTION,
        provenance=(
            "Fine-tune of Qwen/Qwen3-ASR-0.6B @ 5eb144179a02acc5e5ba31e748d22b0cf3e303b0 "
            "(apache-2.0) on the frozen corpus qwen-hi-public-train@v3 (sha 6cfc585d…: "
            "27.3 h cleaned Hindi + 5.92% FLEURS-en retention slice + bounded 0.5-2 s "
            "short-speech slice + 0.5% no-speech negatives; sources CC-BY-4.0/CC0, "
            "attribution recorded in the manifest provenance sidecar); checkpoint-1500, "
            "audio tower frozen. Served as the template-rewrite GGUF Q8_0 export "
            "(model sha256 e54586c4…, official mmproj 41a342b5… byte-shared) through "
            "the pinned llama.cpp b10344 (7a20b417f) llama-server runtime. Weights are "
            "distributed by SEEDING (hash-verified by the store at load) — the artifact "
            "URL is deliberately non-resolvable; deployment seeds the model volume."
        ),
        license=LicenseVerdict(
            license="Apache-2.0",
            commercial_use=True,
            verified_on=date(2026, 8, 18),
            source="https://huggingface.co/Qwen/Qwen3-ASR-0.6B",
        ),
    ),
    ArtifactRecord(
        id="kokoro-82m",
        version=1,
        capability=Capability.SPEECH_SYNTHESIS,
        provenance=(
            "hexgrad/Kokoro-82M v1.0 (Apache-2.0) @ revision f3ff3571…: weights, "
            "config, and voice packs, all SHA-256-pinned from the Hugging Face "
            "distribution. Serves ENGLISH (af_heart, am_michael — espeak-free "
            "misaki G2P, M3 design review §8) and, since the M42 promotion, "
            "HINDI (hf_alpha, hm_psi — sentence-level G2P through the pinned "
            "espeak-ng BINARY at an exec boundary; the GPL python chain stays "
            "banned in-process, build-verified). Training data includes "
            "synthetic audio from third-party models (provenance note, "
            "informational)."
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
#: existed when the ladder was ratified, and re-cited at M5 step 4 to the
#: language-sliced baseline that replaced it: `stt-eval-seed@v2`'s `en`
#: slice, which carries v1's clips byte-identical and reproduces its
#: WER 0.000 exactly. The corpus is authored in-house, so it is OWNED —
#: ours to version and extend, with no third-party licence riding along
#: (ADR-0027 Amendment 3).
_STT_EN_EVIDENCE = LanguageEvidence(
    corpus="stt-eval-seed@v2",
    corpus_ownership=CorpusOwnership.OWNED,
    quality_baseline="2026-08-05-intelliai-stt-en-whisper-small-cpu-v1",
    production_benchmark="2026-08-03-whisper-small-cpu-baseline",
    approval="F-M5-2 — Core Speech Language Policy ladder",
    approved_on=date(2026, 8, 4),
)

_TTS_EN_EVIDENCE = LanguageEvidence(
    corpus="tts-eval-seed@v1",
    corpus_ownership=CorpusOwnership.OWNED,
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

#: Serving-path verdict for the promoted Hindi route: base weights +
#: fine-tune + conversion + runtime, each verified at its own source.
#: End-to-end audio-LLM — no language-specific component rides along.
#: Training-data licenses (CC-BY-4.0 IndicVoices/FLEURS, CC0 Kathbath)
#: attach attribution to the DATA, recorded in the corpus provenance;
#: the served weights remain apache-2.0 derivatives.
_QWEN3_E3_HI_SERVING_PATH = LicenseVerdict(
    license="Apache-2.0",
    commercial_use=True,
    verified_on=date(2026, 8, 18),
    source="https://huggingface.co/Qwen/Qwen3-ASR-0.6B",
    covers=(
        "fine-tuned GGUF weights (apache-2.0 derivative; in-house training on "
        "CC-BY-4.0/CC0 public corpora, attribution in the frozen manifest "
        "provenance) + official mmproj + pinned llama.cpp b10344 runtime (MIT); "
        "end-to-end model, no language-specific component"
    ),
)

#: The promotion's evidence chain, immutable by reference. Numbers on
#: the frozen primary through the real adapter: CER 0.11612 (replicate
#: 0.11750) / WER 0.24064 / 0 hallucinated probes vs the INCUMBENT
#: whisper-small same-day baseline CER 0.37617 / WER 0.66575 — a -69%
#: relative CER improvement, ~15x the replicate noise band. English
#: safety WER 0.0; short-speech, silence, long-audio (300/600 s), and
#: failure-drill batteries in the M23/M24/M25 reports.
_QWEN3_E3_HI_EVIDENCE = LanguageEvidence(
    corpus="stt-hi-public-eval@v1",
    corpus_ownership=CorpusOwnership.ADOPTED,
    quality_baseline="2026-08-18-research-qwen3-asr-0.6b-hi-ft-e3-hi-m23",
    production_benchmark="2026-08-18-qwen3-e3-cpu-ladder",
    approval=(
        "F-M26 — founder promotion decision, 2026-08-19 "
        "(docs/milestones/26-qwen-e3-production-promotion.md); readiness "
        "evidence: docs/research/2026-08-18-qwen3-hi-e3-promotion-readiness.md"
    ),
    approved_on=date(2026, 8, 19),
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

#: Serving-path verdict for the PROMOTED Hindi TTS route (M42). Weights
#: and Hindi voice packs are the same Apache-2.0 artifact; the only
#: Hindi-specific component is espeak-ng — a GPL-3.0 BINARY invoked as a
#: subprocess (constant argv, stdin transport), the M3 §8 posture
#: recorded CLOSED at M35 and reused unchanged for Hindi G2P. No GPL code
#: links into any IntelliAI process (build-verified, isolation-tested).
_KOKORO_HI_SERVING_PATH = LicenseVerdict(
    license="Apache-2.0",
    commercial_use=True,
    verified_on=date(2026, 8, 24),
    source="https://huggingface.co/hexgrad/Kokoro-82M",
    covers=(
        "weights, config, and Hindi voice packs (hf_alpha, hm_psi — SHA-256-pinned "
        "at revision f3ff3571…); Hindi G2P via the pinned espeak-ng 1.51 binary at "
        "an exec boundary (GPL binary invoked as a subprocess, never linked)"
    ),
)

#: The Hindi TTS evidence chain the promotion cites, immutable by
#: reference: the frozen M38 benchmark (61 probes) through the REAL
#: gateway path, judged by the promoted E3 Hindi route with the frozen
#: evaluation methodology. Numbers at promotion (M40 replicate, both
#: approved voices): clean-slice RT-WER 0.0620 (hindi-female) / 0.0547
#: (hindi-male) against the proposed ≤0.08 product gate; long-text
#: ladder 0.0458 / 0.0260 with zero truncation to 1897 chars; stream
#: TTFA 0.77-1.5 s length-independent; zero synthesis failures.
_TTS_HI_EVIDENCE = LanguageEvidence(
    corpus="m38-hindi-tts-probe-texts@v1",
    corpus_ownership=CorpusOwnership.OWNED,
    quality_baseline="2026-08-22-hindi-tts-model-selection",
    production_benchmark="2026-08-24-kokoro-hindi-staging-validation-m40",
    approval=(
        "F-M42 — founder promotion decision, 2026-08-24 "
        "(docs/milestones/42-tts-production-promotion.md); readiness evidence: "
        "docs/milestones/40-hindi-tts-final-staging-validation.md"
    ),
    approved_on=date(2026, 8, 24),
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
    # Hindi: the M26 promotion — the first language to move OFF the
    # incumbent, onto the in-house fine-tuned specialist, on the full
    # M23→M24→M25 evidence chain and the founder's explicit decision.
    # Status stays `available`: the switch changes what honestly serves
    # the existing promise level; `supported` remains a separate, later
    # rung with its own decision. ROLLBACK is a deliberate route change
    # back to whisper-small (registry/proposals.py restates the target
    # verbatim; docs/ops/model-rollout.md) — never an automatic
    # per-request fallback.
    ServingRoute(
        public_model_id="intelliai-stt",
        selector=RouteSelector(language="hi"),
        status=LanguageStatus.AVAILABLE,
        artifact_id="qwen3-asr-0.6b-hi-ft-e3",
        license=_QWEN3_E3_HI_SERVING_PATH,
        evidence=_QWEN3_E3_HI_EVIDENCE,
    ),
    # Arabic entered where every language enters (F-M5-1): `available`
    # on the incumbent — served, not promised.
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
    # Hindi synthesis: the M42 promotion — the second language to reach
    # the product, on the SAME artifact the English route serves (M38
    # chose extending the incumbent over a second engine; M39 built it;
    # M40 validated it). Status stays `available`: every language enters
    # the ladder there (F-M5-1), and `supported` remains a separate,
    # later rung with its own decision. ROLLBACK is a deliberate route
    # change back to refusal (registry/proposals.py restates the target
    # verbatim; docs/ops/model-rollout.md) — never a silent fallback.
    ServingRoute(
        public_model_id="intelliai-tts",
        selector=RouteSelector(language="hi"),
        status=LanguageStatus.AVAILABLE,
        artifact_id="kokoro-82m",
        license=_KOKORO_HI_SERVING_PATH,
        evidence=_TTS_HI_EVIDENCE,
    ),
    ServingRoute(
        public_model_id="intelliai-tts",
        selector=RouteSelector(language="ar"),
        status=LanguageStatus.UNAVAILABLE,
    ),
)

# Public voice identities. M35 naming: `english-female` / `english-male`
# are the launch names — product-friendly, neutral, never engine tokens,
# claiming no proprietary voice identity. The M3 placeholders remain
# served as legacy aliases: voice ids are permanent API surface, so
# renaming is ADDITION, never removal (the append-only voice-metadata
# law). Both names resolve to the same rendering.
_VOICES = (
    PublicVoiceRecord(
        id="english-female",
        model="intelliai-tts",
        languages=("en",),
        description="Female English voice",
        released=date(2026, 8, 20),
    ),
    PublicVoiceRecord(
        id="english-male",
        model="intelliai-tts",
        languages=("en",),
        description="Male English voice",
        released=date(2026, 8, 20),
    ),
    PublicVoiceRecord(
        id="reference-alto",
        model="intelliai-tts",
        languages=("en",),
        description="Female English voice (legacy alias of english-female)",
        released=date(2026, 8, 3),
    ),
    PublicVoiceRecord(
        id="reference-bass",
        model="intelliai-tts",
        languages=("en",),
        description="Male English voice (legacy alias of english-male)",
        released=date(2026, 8, 3),
    ),
    # The M42 promotion's Hindi pair. Product names only: the engine
    # voice packs behind them never cross this plane, and each record
    # declares exactly one language, so `resolve_voice` routes them
    # through the Hindi route (the voice IS the routing key).
    PublicVoiceRecord(
        id="hindi-female",
        model="intelliai-tts",
        languages=("hi",),
        description="Female Hindi voice",
        released=date(2026, 8, 24),
    ),
    PublicVoiceRecord(
        id="hindi-male",
        model="intelliai-tts",
        languages=("hi",),
        description="Male Hindi voice",
        released=date(2026, 8, 24),
    ),
)


@lru_cache(maxsize=1)
def default_registry() -> Registry:
    """The validated platform registry; composition failures abort startup."""
    return Registry(artifacts=_ARTIFACTS, models=_MODELS, voices=_VOICES, routes=_ROUTES)
