"""Runtime failure taxonomy — transport-free by design.

Four types cover every way a runtime can fail *as seen from the gateway*.
No HTTP status codes live here, and no retry policy: whether `overloaded`
is retried, and what status the client sees, are gateway decisions
(ADR-0009 translation), informed by the type but never dictated by the
runtime.
"""

from enum import StrEnum, unique

from pydantic import Field

from intelliai_runtime_contract.base import ContractModel
from intelliai_runtime_contract.metadata import RuntimeMetadata


@unique
class RuntimeErrorType(StrEnum):
    """Everything a runtime can say about its own failure."""

    INVALID_INPUT = "invalid_input"  # the request itself cannot be served
    NOT_READY = "not_ready"  # model not loaded / warming up
    OVERLOADED = "overloaded"  # healthy but at capacity right now
    INTERNAL = "internal"  # unexpected failure; details stay in runtime logs


class RuntimeErrorResponse(ContractModel):
    """The failure envelope a runtime returns instead of a result."""

    type: RuntimeErrorType
    message: str = Field(min_length=1)  # safe for operators; never internals/secrets
    param: str | None = None  # offending request field, when known
    runtime: RuntimeMetadata
