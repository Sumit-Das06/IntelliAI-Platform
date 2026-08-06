"""ORM models — the platform's persistent nouns.

Charter: this package owns table definitions and relationships, nothing
else. No queries (repositories), no business rules (services), no HTTP
shapes (api schemas). Importing this package registers every mapper with
``Base.metadata`` — Alembic autogenerate and tests rely on that, so every
new model module MUST be imported here.
"""

from intelliai_api.db.models.api_key import ApiKey
from intelliai_api.db.models.membership import Membership, MembershipRole
from intelliai_api.db.models.organization import Organization
from intelliai_api.db.models.speech_sample import (
    ClientSource,
    CorrectionSource,
    SampleStatus,
    SpeechSample,
    SpeechSampleEvent,
)
from intelliai_api.db.models.usage_event import (
    UsageEvent,
    UsageOrigin,
    UsageOutcome,
    UsageQuantity,
)
from intelliai_api.db.models.usage_rollup import UsageRollup
from intelliai_api.db.models.user import User

__all__ = [
    "ApiKey",
    "ClientSource",
    "CorrectionSource",
    "Membership",
    "MembershipRole",
    "Organization",
    "SampleStatus",
    "SpeechSample",
    "SpeechSampleEvent",
    "UsageEvent",
    "UsageOrigin",
    "UsageOutcome",
    "UsageQuantity",
    "UsageRollup",
    "User",
]
