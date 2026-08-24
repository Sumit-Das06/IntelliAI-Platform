"""Prepared catalog changes awaiting a founder decision — NEVER registered.

**One proposal is pending: Hindi TTS (M39).** The M38 research decision
(Kokoro Hindi, founder-approved voices hindi-female=hf_alpha /
hindi-male=hm_psi) is implemented for the LOCAL/STAGING tier only: the
staging profile composes the two Hindi voice records and flips the
`intelliai-tts x hi` route from its honest refusal to the kokoro-82m
artifact. The LIVE catalog keeps refusing Hindi TTS — production
promotion is a separate, later founder decision, exactly like E3's
M24→M26 path (a test pins the live refusal until that commit lands).

Also here, deliberately:

- ``ROLLBACK_HINDI_ROUTE`` — the reviewed rollback target for the
  ACTIVE Hindi STT route (M26). Rolling back is the git revert of the
  promotion commit (docs/ops/model-rollout.md); a test pins the
  target. Automatic per-request fallback does not exist (M16).
- ``staging_registry()`` — the staging profile's composition hook
  (``INTELLIAI_REGISTRY_PROFILE=staging``, refused under
  ``INTELLIAI_ENV=prod``): where every candidate route composes for
  local/staging verification before its own promotion commit.
"""

from datetime import date
from typing import Final

from intelliai_api.registry.catalog import _ARTIFACTS, _MODELS, _ROUTES, _VOICES
from intelliai_api.registry.records import (
    CorpusOwnership,
    LanguageEvidence,
    LanguageStatus,
    LicenseVerdict,
    PublicVoiceRecord,
    RouteSelector,
    ServingRoute,
)
from intelliai_api.registry.registry import Registry

#: The evidence.approval sentinel (M24 mechanism): a proposal is
#: constructible only in this pending form; the production promotion
#: diff MUST replace it with the founder decision reference, and a test
#: refuses a LIVE registry that ever carries the sentinel.
APPROVAL_PENDING: Final = (
    "PENDING founder decision — prepared by Milestone 39 "
    "(docs/research/2026-08-22-hindi-tts-model-selection.md; implementation "
    "evidence docs/milestones/39-kokoro-hindi-tts-local-web.md)"
)

#: Serving-path verdict for the STAGING Hindi TTS route. The weights and
#: Hindi voice packs are the same Apache-2.0 kokoro-82m artifact
#: (SHA-pinned, artifact spec v2); the Hindi-specific component is
#: espeak-ng — a GPL-3.0 BINARY behind an exec boundary (subprocess,
#: constant argv, stdin transport), the M3 §8 posture recorded CLOSED at
#: M35 for the English OOV fallback and reused unchanged for Hindi G2P.
#: No GPL code links into any IntelliAI process.
_KOKORO_HI_SERVING_PATH: Final = LicenseVerdict(
    license="Apache-2.0",
    commercial_use=True,
    verified_on=date(2026, 8, 24),
    source="https://huggingface.co/hexgrad/Kokoro-82M",
    covers=(
        "weights, config, and Hindi voice packs (hf_alpha, hm_psi — SHA-pinned, "
        "artifact v2); Hindi G2P via the pinned espeak-ng 1.51 binary at the M35 "
        "exec boundary (GPL binary invoked as a subprocess, never linked)"
    ),
)

#: The M38→M39 evidence chain for the staging route: the frozen M38
#: benchmark through the REAL gateway path, judged by the promoted E3
#: route with the frozen evaluation methodology.
_KOKORO_HI_EVIDENCE: Final = LanguageEvidence(
    # Research-instrument probe set (61 fixed cases); graduation to an
    # evaluation-plane corpus rides the production promotion.
    corpus="m38-hindi-tts-probe-texts@v1",
    corpus_ownership=CorpusOwnership.OWNED,
    quality_baseline="2026-08-22-hindi-tts-model-selection (M38 clean RT-WER 0.045-0.071)",
    production_benchmark="research/experiments/39-hindi-tts-local-web/evidence",
    approval=APPROVAL_PENDING,
    approved_on=date(2026, 8, 24),
)

#: THE PROPOSED VOICES: the M38-approved pair, product names only —
#: engine pack tokens never cross the product plane. Exactly one
#: language each, so ``resolve_voice`` routes them through the Hindi
#: route (the voice IS the routing key).
HINDI_TTS_VOICES: Final = (
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

#: THE PROPOSED ROUTE: Hindi TTS on the incumbent artifact. Status
#: ``available`` — every language enters the ladder there (F-M5-1);
#: `supported` is a separate, later rung.
HINDI_TTS_ROUTE: Final = ServingRoute(
    public_model_id="intelliai-tts",
    selector=RouteSelector(language="hi"),
    status=LanguageStatus.AVAILABLE,
    artifact_id="kokoro-82m",
    license=_KOKORO_HI_SERVING_PATH,
    evidence=_KOKORO_HI_EVIDENCE,
)

#: THE FUTURE PROMOTION, prepared (M40) exactly like E3's was at M24 —
#: one reviewed, revertible catalog commit that moves three things
#: together (docs/ops/model-rollout.md "PREPARED promotion"):
#:   1. catalog.py: append ``HINDI_TTS_VOICES`` to ``_VOICES`` and
#:      replace the hi refusal route with ``HINDI_TTS_ROUTE``;
#:   2. the route's ``evidence.approval``: replace ``APPROVAL_PENDING``
#:      with the founder decision reference (a test refuses a live
#:      registry that ever carries the sentinel);
#:   3. the guards/tests: flip the production-refusal pins to
#:      production-serving pins in the same commit.
#: No artifact re-admission is needed (kokoro-82m is already registered
#: and its v2 spec carries both Hindi packs), and no image change rides
#: the commit. NOTE: the promotion changes only the CATALOG; actually
#: serving TTS in production additionally needs the separate TTS
#: production-launch gate (prod overlay tts block, Hostinger) — two
#: knobs, deliberately never one commit.

#: THE ROLLBACK TARGET for that future promotion: today's live refusal,
#: restated verbatim (the M26 rollback discipline). Reverting the
#: promotion commit must land exactly this route — and a test pins that
#: this record equals the live catalog's current hi TTS route, so the
#: revert target stays reviewed for as long as the proposal is pending.
ROLLBACK_HINDI_TTS_ROUTE: Final = ServingRoute(
    public_model_id="intelliai-tts",
    selector=RouteSelector(language="hi"),
    status=LanguageStatus.UNAVAILABLE,
)


def staging_registry() -> Registry:
    """The live catalog PLUS the pending M39 Hindi TTS proposal.

    Composition, not mutation: the live tuples stay untouched; staging
    swaps the one refused route for the proposed one and appends the
    two proposed voices. Production (`default_registry()`) keeps
    refusing Hindi TTS until the promotion commit lands there.
    """
    routes = tuple(
        HINDI_TTS_ROUTE
        if (route.public_model_id == "intelliai-tts" and route.selector.language == "hi")
        else route
        for route in _ROUTES
    )
    return Registry(
        artifacts=_ARTIFACTS,
        models=_MODELS,
        voices=_VOICES + HINDI_TTS_VOICES,
        routes=routes,
    )


#: THE ROLLBACK TARGET for the active Hindi route (M26): reverting the
#: promotion commit must land exactly this route, and the incumbent
#: artifact must still be pinned and cached (verified by the rollout
#: runbook's procedure). Whisper-small remains registered in the live
#: catalog as the English/default artifact, so the rollback needs no
#: artifact re-admission — only the route change.
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
