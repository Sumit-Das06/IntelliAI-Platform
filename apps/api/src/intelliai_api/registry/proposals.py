"""Prepared catalog changes awaiting a founder decision — NEVER registered.

**No proposal is currently pending.** The E3 Hindi promotion this
module prepared (M17 mechanism, M24 candidate) was APPROVED by the
founder on 2026-08-19 and ACTIVATED by the Milestone 26 promotion
commit: the live catalog now carries `qwen3-asr-0.6b-hi-ft-e3` and the
Hindi route with the founder's approval record riding on the route
evidence (registry/catalog.py). The superseded proposal texts live in
git history and the M17/M18/M24 reports.

What remains here, deliberately:

- ``ROLLBACK_HINDI_ROUTE`` — the reviewed rollback target for the now
  ACTIVE Hindi route. Rolling back is the git revert of the promotion
  commit (docs/ops/model-rollout.md), and its result must equal this
  record exactly; a test pins that. Rollback is always a deliberate
  route change — automatic per-request fallback does not exist, by
  the standing M16 decision.
- ``staging_registry()`` — the staging profile's composition hook.
  With no pending proposal it composes exactly the live catalog, so
  the local production-shaped stack (M25) and any future staging shape
  serve what production would serve. The NEXT promotion candidate
  activates here first, exactly as E3 did.
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

    No proposal is pending after the M26 promotion, so this is exactly
    the reviewed live catalog. The function (and the
    ``INTELLIAI_REGISTRY_PROFILE=staging`` plumbing that reaches it,
    refused under ``INTELLIAI_ENV=prod``) stays: it is where the next
    candidate route composes for local/staging verification before its
    own promotion commit.
    """
    return default_registry()


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
