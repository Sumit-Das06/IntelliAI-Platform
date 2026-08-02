"""The one model discipline every contract message obeys.

Frozen: a validated message is immutable — nothing downstream can quietly
rewrite what was said on the wire.

Tolerant reader (extra="ignore"): unknown fields are dropped, never errors.
This is what lets gateway and runtimes upgrade on independent schedules
(additive-with-defaults evolution, ADR-0016) — and because an undeclared
field is discarded on read, sending one is useless, which closes the
side-channel that turns shared schemas into dumping grounds.
"""

from pydantic import BaseModel, ConfigDict


class ContractModel(BaseModel):
    """Base for every schema in the runtime contract."""

    model_config = ConfigDict(frozen=True, extra="ignore")
