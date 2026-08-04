"""Unserved demand: what customers asked for and did not get.

A refusal is the only evidence we will ever have that someone wanted a
language we do not serve. Refuse silently and the Language Policy is
steered by opinion; record the refusal and it is steered by what
customers actually asked for — which is the whole reason the ladder has
a middle rung rather than a boolean (ADR-0027).

**No billable event is produced, and none ever should be.** A refusal
crosses no plane, runs no inference, and costs the customer nothing;
writing it to the usage ledger would break Commercial Completeness
(every billable record answers to one served request). This is a
*request-event* fact, and until request events are persisted — M4's
registered debt, which this is now a second caller for — the structured
event stream is their store. The event name and fields are chosen so
that persisting them later is a move, not a redesign.
"""

import structlog

from intelliai_api.registry import LanguageNotSupportedError
from intelliai_api.services.auth import AuthContext
from intelliai_runtime_contract import Capability

logger = structlog.get_logger(__name__)

#: The one event name analytics joins on. Changing it breaks a query
#: someone will have written; treat it as vocabulary, not as a string.
LANGUAGE_REFUSED = "language.refused"


def record_language_demand(
    *,
    auth: AuthContext,
    capability: Capability,
    refusal: LanguageNotSupportedError,
) -> None:
    """Record one refused language request as demand evidence."""
    logger.info(
        LANGUAGE_REFUSED,
        organization_id=auth.organization_public_id,
        capability=capability.value,
        model=refusal.model_id,
        language=refusal.language,
        served_languages=list(refusal.served),
    )
