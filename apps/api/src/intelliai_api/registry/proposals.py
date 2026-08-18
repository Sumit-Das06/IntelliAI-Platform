"""Prepared catalog changes awaiting a founder decision — NEVER registered.

Milestone 17 prepared the original Hindi switching proposal around the
BASE Qwen3-ASR artifact. Milestone 24 SUPERSEDES it with the fine-tuned
retention-mix candidate `qwen3-asr-0.6b-hi-ft-e3@v1` — the program's
first candidate to pass all eight research gates (M23) — so the exact
catalog change a promotion would land is prepared HERE, validated by
tests, and deliberately unreachable from ``default_registry()``. The
superseded base-qwen proposal lives in git history and the M17/M18
reports; it was never approved and never served a customer.

Activating a proposal is the promotion commit itself, and it stays a
small reviewable diff by construction: add the artifact to catalog
``_ARTIFACTS``, replace the corresponding route in ``_ROUTES``, and
replace the evidence ``approval`` sentinel with the founder decision
reference. Rollback is the git revert of that same commit — the
incumbent's route below is restated verbatim so the revert target is
part of the reviewed record (docs/ops/model-rollout.md).

Nothing in this module changes what serves customers. A test pins that:
the live registry must keep resolving Hindi to the incumbent until the
promotion commit lands.
"""

from datetime import date
from typing import Final

from intelliai_api.registry.catalog import _ARTIFACTS, _MODELS, _ROUTES, _VOICES
from intelliai_api.registry.records import (
    ArtifactRecord,
    CorpusOwnership,
    LanguageEvidence,
    LanguageStatus,
    LicenseVerdict,
    RouteSelector,
    ServingRoute,
)
from intelliai_api.registry.registry import Registry
from intelliai_runtime_contract import Capability

#: The evidence.approval sentinel. A proposal is constructible only in
#: this pending form; the promotion diff MUST replace it with the actual
#: founder decision reference, and a test refuses a live registry that
#: ever carries the sentinel.
APPROVAL_PENDING: Final = (
    "PENDING founder decision — prepared by Milestone 24 "
    "(docs/research/2026-08-18-qwen3-hi-e3-promotion-readiness.md)"
)

#: The candidate artifact, identity pinned end to end. Weights: the M23
#: retention-mix fine-tune of the pinned base, exported by the
#: byte-exact template rewrite onto the official GGUF structure (the
#: pipeline's control reproduced the official base artifact
#: byte-for-byte). Runtime: the pinned llama.cpp b10344 build per
#: platform (hash tables live with the engine adapter —
#: services/stt-runtime engines/qwen3_asr.py). Identity re-verified by
#: research/experiments/24-e3-promotion/identity.json.
QWEN3_E3_ARTIFACT: Final = ArtifactRecord(
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
        "the pinned llama.cpp b10344 (7a20b417f) llama-server runtime"
    ),
    license=LicenseVerdict(
        license="Apache-2.0",
        commercial_use=True,
        verified_on=date(2026, 8, 18),
        source="https://huggingface.co/Qwen/Qwen3-ASR-0.6B",
    ),
)

#: Serving-path verdict for the Hindi route: base weights + fine-tune +
#: conversion + runtime, each verified at its own source. End-to-end
#: audio-LLM — no language-specific component rides along (no G2P, no
#: lexicon). Training data licenses (CC-BY-4.0 IndicVoices/FLEURS, CC0
#: Kathbath) attach attribution obligations to the DATA, recorded in the
#: corpus provenance; the served weights remain apache-2.0 derivatives.
_QWEN3_E3_HI_SERVING_PATH: Final = LicenseVerdict(
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

#: The quality baseline the route promotion cites — the committed,
#: reproducible evidence chain, immutable by reference: frozen manifest
#: sha cf643146…, ruler cer_unicode/unicode_generic@v2, greedy decode,
#: research-harness route through the product runtime. Numbers: CER
#: 0.11612 (replicate 0.11750) / WER 0.24064 / 0 probe words / 0
#: failures / RTF 0.218 — vs the INCUMBENT whisper-small baseline CER
#: 0.36288 / WER 0.65899 (15C) and the base-qwen reference 0.1457 (15E).
#: English safety WER 0.0 (M23); short-speech and silence batteries in
#: the M23 report.
QWEN3_E3_HI_EVIDENCE: Final = LanguageEvidence(
    corpus="stt-hi-public-eval@v1",
    corpus_ownership=CorpusOwnership.ADOPTED,
    quality_baseline="2026-08-18-research-qwen3-asr-0.6b-hi-ft-e3-hi-m23",
    production_benchmark="2026-08-18-qwen3-e3-cpu-ladder",
    approval=APPROVAL_PENDING,
    approved_on=date(2026, 8, 18),
)

#: THE PROPOSED ROUTE: Hindi to the E3 candidate — E3-SPECIFIC, never
#: the generic base artifact. Status stays ``available`` — `supported`
#: is a separate, later rung with its own founder decision; the switch
#: itself does not promise anything new, it changes what honestly
#: serves the existing promise level.
QWEN3_E3_HINDI_ROUTE: Final = ServingRoute(
    public_model_id="intelliai-stt",
    selector=RouteSelector(language="hi"),
    status=LanguageStatus.AVAILABLE,
    artifact_id="qwen3-asr-0.6b-hi-ft-e3",
    license=_QWEN3_E3_HI_SERVING_PATH,
    evidence=QWEN3_E3_HI_EVIDENCE,
)


def staging_registry() -> Registry:
    """The live catalog PLUS the prepared proposals — staging only.

    This is the exact composition the promotion commit would make
    permanent, built at runtime for local/staging verification
    (Milestone 18 mechanism, Milestone 24 candidate). It is reachable
    exclusively through ``INTELLIAI_REGISTRY_PROFILE=staging``, which
    the settings layer refuses under ``INTELLIAI_ENV=prod`` and which
    no committed compose file sets (guard-tested). Production keeps
    composing ``default_registry()`` — the reviewed catalog, nothing
    else.
    """
    routes = tuple(
        QWEN3_E3_HINDI_ROUTE
        if (route.public_model_id == "intelliai-stt" and route.selector.language == "hi")
        else route
        for route in _ROUTES
    )
    return Registry(
        artifacts=(*_ARTIFACTS, QWEN3_E3_ARTIFACT),
        models=_MODELS,
        voices=_VOICES,
        routes=routes,
    )


#: THE ROLLBACK TARGET, restated verbatim from today's live catalog: the
#: revert of the promotion commit must land exactly this route, and the
#: incumbent artifact must still be pinned and cached (verified by the
#: rollout runbook's procedure).
ROLLBACK_HINDI_ROUTE: Final = ServingRoute(
    public_model_id="intelliai-stt",
    selector=RouteSelector(language="hi"),
    status=LanguageStatus.AVAILABLE,
    artifact_id="whisper-small",
    license=LicenseVerdict(
        license="MIT",
        commercial_use=True,
        verified_on=date(2026, 7, 31),
        source="https://huggingface.co/Systran/faster-whisper-small",
        covers=(
            "weights and CTranslate2 conversion; end-to-end model, no language-specific component"
        ),
    ),
)
