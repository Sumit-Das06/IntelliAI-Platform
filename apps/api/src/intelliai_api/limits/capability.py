"""The capability seam of admission control.

Capability limits cannot live with the identity-scoped ones: the
capability is not known until the registry has resolved the request
(§13.2). This is the thin object capability services hold, so that a
service never learns what Redis, a plan, or a token bucket is — it asks
one question and gets an answer or an error.

Capability-agnostic by construction: the identity is
``organization:capability`` built from a string. A capability that does
not exist yet — OCR, vision, chat, embeddings — is limited correctly the
day it ships, with no change here.

Takes plain identifiers rather than an ``AuthContext`` on purpose. The
limits package must not depend on the services layer: it is imported by
the ORM (an organization carries a plan), and a dependency on services
would close a cycle. Explicit parameters keep the direction one-way.
"""

import structlog

from intelliai_api.limits.controller import AdmissionController, refuse
from intelliai_api.limits.plans import plan_for
from intelliai_api.limits.rules import LimitRule, LimitScope

logger = structlog.get_logger(__name__)


class CapabilityAdmission:
    def __init__(self, controller: AdmissionController) -> None:
        self._controller = controller

    async def check_capability(
        self, *, organization_id: str, plan_id: str, capability: str
    ) -> None:
        """Refuse with 429 if this tenant is over its allowance for this capability.

        Scoped per organization AND per capability, so a customer
        saturating transcription cannot also exhaust their synthesis
        allowance — different capacity, different budget.
        """
        plan = plan_for(plan_id)
        decision = await self._controller.check(
            [
                LimitRule(
                    scope=LimitScope.CAPABILITY,
                    identity=f"{organization_id}:{capability}",
                    requests_per_minute=plan.capability_requests_per_minute,
                    burst=plan.burst,
                )
            ]
        )
        if not decision.allowed:
            logger.info(
                "ratelimit.capability_refused",
                organization_id=organization_id,
                capability=capability,
            )
            raise refuse(decision)
