"""Runtime operational identity — intentionally small, and staying that way.

Metadata answers exactly one operational question: *which service, at which
version, speaking which contract version, produced this message?* It is
never a transport for payload — outputs, usage, model behavior, and engine
details belong in the envelope's typed fields. Any new field here must be
purely operational and amends ADR-0016; growth by convenience is a rejected
change, not a small one.
"""

from pydantic import Field

from intelliai_runtime_contract.base import ContractModel


class RuntimeMetadata(ContractModel):
    """Who served: capability-named service, its version, its contract."""

    service: str = Field(min_length=1)  # e.g. "stt-runtime" — never an engine name
    service_version: str = Field(min_length=1)
    contract_version: int = Field(ge=1)
