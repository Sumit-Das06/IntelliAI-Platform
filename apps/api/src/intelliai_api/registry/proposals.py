"""Prepared catalog changes awaiting a founder decision — NEVER registered.

Milestone 17: the Hindi switching decision has its complete evidence
file (15E accuracy, 16 operations, 17 canary preparation), so the exact
catalog change a promotion would land is prepared HERE, validated by
tests, and deliberately unreachable from ``default_registry()``.

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

from intelliai_api.registry.records import (
    ArtifactRecord,
    CorpusOwnership,
    LanguageEvidence,
    LanguageStatus,
    LicenseVerdict,
    RouteSelector,
    ServingRoute,
)
from intelliai_runtime_contract import Capability

#: The evidence.approval sentinel. A proposal is constructible only in
#: this pending form; the promotion diff MUST replace it with the actual
#: founder decision reference, and a test refuses a live registry that
#: ever carries the sentinel.
APPROVAL_PENDING: Final = (
    "PENDING founder decision — prepared by Milestone 17 "
    "(docs/research/2026-08-12-qwen3-production-canary-prep.md)"
)

#: The candidate artifact, identity pinned end to end. Weights: the
#: OFFICIAL ggml-org GGUF conversion of Qwen/Qwen3-ASR-0.6B. Runtime:
#: the pinned llama.cpp b10344 build per platform (hash tables live with
#: the engine adapter — services/stt-runtime engines/qwen3_asr.py).
QWEN3_ASR_ARTIFACT: Final = ArtifactRecord(
    id="qwen3-asr-0.6b",
    version=1,
    capability=Capability.TRANSCRIPTION,
    provenance=(
        "Qwen/Qwen3-ASR-0.6B @ 5eb144179a02acc5e5ba31e748d22b0cf3e303b0 (apache-2.0), "
        "served as the official ggml-org GGUF Q8_0 conversion "
        "(ggml-org/Qwen3-ASR-0.6B-GGUF @ 928ab958557df9aa2ef1c93e0e83c7ad0933fae2; "
        "model sha256 bca25981…, mmproj sha256 41a342b5…) through the pinned "
        "llama.cpp b10344 (7a20b417f) llama-server runtime"
    ),
    license=LicenseVerdict(
        license="Apache-2.0",
        commercial_use=True,
        verified_on=date(2026, 8, 12),
        source="https://huggingface.co/Qwen/Qwen3-ASR-0.6B",
    ),
)

#: Serving-path verdict for the Hindi route: weights + conversion +
#: runtime, each verified at its own source. End-to-end audio-LLM — no
#: language-specific component rides along (no G2P, no lexicon).
_QWEN3_HI_SERVING_PATH: Final = LicenseVerdict(
    license="Apache-2.0",
    commercial_use=True,
    verified_on=date(2026, 8, 12),
    source="https://huggingface.co/ggml-org/Qwen3-ASR-0.6B-GGUF",
    covers=(
        "GGUF weights and mmproj (apache-2.0, ggml-org conversion verified against "
        "upstream LFS pins) + pinned llama.cpp b10344 runtime (MIT); end-to-end "
        "model, no language-specific component"
    ),
)

#: The quality baseline the route promotion cites — the committed,
#: reproducible evidence chain, immutable by reference: frozen manifest
#: sha cf643146…, ruler cer_unicode/unicode_generic@v2, greedy decode,
#: research-harness route through the product runtime. Numbers: CER
#: 0.1457 (replicate 0.1446) / WER 0.2851 / 0 probe words / 0 failures /
#: RTF 0.207 vs the incumbent baseline CER 0.3629 (15C).
QWEN3_HI_EVIDENCE: Final = LanguageEvidence(
    corpus="stt-hi-public-eval@v1",
    corpus_ownership=CorpusOwnership.ADOPTED,
    quality_baseline="2026-08-12-research-qwen3-asr-0.6b-hi-15e",
    production_benchmark="2026-08-12-qwen3-asr-0.6b-cpu-ladder",
    approval=APPROVAL_PENDING,
    approved_on=date(2026, 8, 12),
)

#: THE PROPOSED ROUTE: Hindi to the challenger. Status stays
#: ``available`` — `supported` is a separate, later rung with its own
#: founder decision; the switch itself does not promise anything new,
#: it changes what honestly serves the existing promise level.
QWEN3_HINDI_ROUTE: Final = ServingRoute(
    public_model_id="intelliai-stt",
    selector=RouteSelector(language="hi"),
    status=LanguageStatus.AVAILABLE,
    artifact_id="qwen3-asr-0.6b",
    license=_QWEN3_HI_SERVING_PATH,
    evidence=QWEN3_HI_EVIDENCE,
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
