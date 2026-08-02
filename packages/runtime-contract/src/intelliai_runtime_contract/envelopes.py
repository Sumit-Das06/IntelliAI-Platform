"""Success envelope and its vocabulary: usage, timing, and the generic shape.

Every successful runtime response is the same envelope around a
capability-specific output: what was produced, which model produced it,
what it cost (usage), how long it took (timing), and who served it
(metadata). Requests carry no generic envelope — media travels by
transport, correlation ids travel as transport concerns, so the request
contract *is* the capability's params schema.
"""

from enum import StrEnum, unique

from pydantic import Field

from intelliai_runtime_contract.base import ContractModel
from intelliai_runtime_contract.metadata import RuntimeMetadata


@unique
class UsageUnit(StrEnum):
    """Billing vocabulary — append-only, members land with the capability
    that bills in them."""

    AUDIO_SECONDS = "audio_seconds"


class Usage(ContractModel):
    """One measured quantity the gateway may account and bill."""

    unit: UsageUnit
    amount: float = Field(ge=0)


class RuntimeTiming(ContractModel):
    """Wall-clock the runtime observed. Stage names are owned by the
    runtime (its pipeline shape is its own business); total is the
    cross-runtime comparable number."""

    total_ms: float = Field(ge=0)
    stages: dict[str, float] = Field(default_factory=dict)


class RuntimeResponse[OutputT: ContractModel](ContractModel):
    """The one success envelope every runtime returns.

    `model` is the identifier of the loaded artifact that served the
    request — registry vocabulary, never an engine or library name.
    """

    output: OutputT
    model: str = Field(min_length=1)
    usage: tuple[Usage, ...] = ()
    timing: RuntimeTiming
    runtime: RuntimeMetadata
