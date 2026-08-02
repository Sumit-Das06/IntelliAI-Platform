"""The permanent language between the API gateway and every AI runtime.

Schemas and vocabulary only — no networking, no transport, no logic
(ADR-0016). Everything public is exported here; consumers import from the
package root and never from submodules.
"""

from intelliai_runtime_contract.base import ContractModel
from intelliai_runtime_contract.capabilities import Capability
from intelliai_runtime_contract.envelopes import (
    RuntimeResponse,
    RuntimeTiming,
    Usage,
    UsageUnit,
)
from intelliai_runtime_contract.errors import RuntimeErrorResponse, RuntimeErrorType
from intelliai_runtime_contract.metadata import RuntimeMetadata
from intelliai_runtime_contract.transcription import (
    TranscriptionRequest,
    TranscriptionResponse,
    TranscriptionResult,
    TranscriptionSegment,
)
from intelliai_runtime_contract.version import CONTRACT_VERSION

__version__ = "0.1.0"

__all__ = [
    "CONTRACT_VERSION",
    "Capability",
    "ContractModel",
    "RuntimeErrorResponse",
    "RuntimeErrorType",
    "RuntimeMetadata",
    "RuntimeResponse",
    "RuntimeTiming",
    "TranscriptionRequest",
    "TranscriptionResponse",
    "TranscriptionResult",
    "TranscriptionSegment",
    "Usage",
    "UsageUnit",
]
