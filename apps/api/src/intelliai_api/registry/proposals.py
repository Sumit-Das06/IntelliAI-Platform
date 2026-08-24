"""Prepared catalog changes awaiting a founder decision — NEVER registered.

**No proposal is currently pending.** The Hindi TTS promotion this
module prepared (M39 implementation, M40 validation) was APPROVED by
the founder on 2026-08-24 and ACTIVATED by the Milestone 42 promotion
commit: the live catalog now carries the `hindi-female` / `hindi-male`
voices and the `intelliai-tts x hi` route on `kokoro-82m`, with the
founder's approval record riding on the route evidence
(registry/catalog.py). The superseded proposal text lives in git
history and the M39/M40 reports — exactly like the E3 STT promotion
before it (M24 → M26).

What remains here, deliberately:

- ``ROLLBACK_HINDI_ROUTE`` — the reviewed rollback target for the
  ACTIVE Hindi STT route (M26).
- ``ROLLBACK_TTS_PRODUCTION_ROUTE`` — the reviewed rollback target for
  the ACTIVE Hindi TTS route (M42): the honest refusal production
  served before the promotion, restated verbatim so the revert target
  is part of the reviewed record. Rolling back either route is the git
  revert of its promotion commit (docs/ops/model-rollout.md); a test
  pins each target. Automatic per-request fallback does not exist, by
  the standing M16 decision.
- ``staging_registry()`` — the staging profile's composition hook
  (``INTELLIAI_REGISTRY_PROFILE=staging``, refused under
  ``INTELLIAI_ENV=prod``). With no pending proposal it composes exactly
  the live catalog, so the local production-shaped stack serves what
  production would serve. The NEXT candidate activates here first.
"""

from datetime import date
from typing import Final

from intelliai_api.registry.catalog import default_registry
from intelliai_api.registry.records import (
    LanguageStatus,
    LicenseVerdict,
    RouteSelector,
    ServingRoute,
)
from intelliai_api.registry.registry import Registry


def staging_registry() -> Registry:
    """The live catalog PLUS any prepared proposals — staging only.

    No proposal is pending after the M42 promotion, so this is exactly
    the reviewed live catalog. The function (and the
    ``INTELLIAI_REGISTRY_PROFILE=staging`` plumbing that reaches it,
    refused under ``INTELLIAI_ENV=prod``) stays: it is where the next
    candidate route composes for local/staging verification before its
    own promotion commit.
    """
    return default_registry()


#: THE ROLLBACK TARGET for the active Hindi STT route (M26): reverting
#: the promotion commit must land exactly this route, and the incumbent
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

#: THE ROLLBACK TARGET for the active Hindi TTS route (M42): the honest
#: refusal production served before the promotion. Reverting the
#: promotion commit must land exactly this route — a whole-language
#: rollback, never a half-promoted state: the two Hindi voice records
#: leave the catalog in the same revert, so a `hindi-female` request
#: answers `voice_not_found` before any plane crossing (test-pinned)
#: instead of resolving to a language the catalog refuses. English TTS
#: is untouched by that revert — it was already the catalog's supported
#: route before M42, and the promotion never changed it.
ROLLBACK_TTS_PRODUCTION_ROUTE: Final = ServingRoute(
    public_model_id="intelliai-tts",
    selector=RouteSelector(language="hi"),
    status=LanguageStatus.UNAVAILABLE,
)
