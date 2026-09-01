"""HTTP binding constants for runtime-contract v1 (documented in ADR-0016).

These are deliberately OUTSIDE packages/runtime-contract: the contract is
transport-free; the binding belongs to the services that speak HTTP. The
gateway's RuntimeClient (step 6) pins the same names with a cross-checked
test — where these constants' permanent shared home lives is decided
there.

Statuses here are the INTERNAL binding, never the public API: the gateway
re-maps runtime errors into the public envelope (ADR-0009).
"""

from typing import Final

from intelliai_runtime_contract import RuntimeErrorType

HEADER_REQUEST_ID: Final = "X-Request-ID"
HEADER_CONTRACT_VERSION: Final = "X-Runtime-Contract-Version"

ROUTE_TRANSCRIBE: Final = "/v1/transcribe"
ROUTE_REALTIME: Final = "/v1/realtime"  # WebSocket sessions (M53), flag-gated
ROUTE_CORRECT: Final = "/v1/correct"  # smart correction (M57), flag-gated
PART_FILE: Final = "file"  # multipart part: the audio bytes
PART_PARAMS: Final = "params"  # multipart part: TranscriptionRequest as JSON

STATUS_BY_ERROR_TYPE: Final[dict[RuntimeErrorType, int]] = {
    RuntimeErrorType.INVALID_INPUT: 400,
    RuntimeErrorType.NOT_READY: 503,
    RuntimeErrorType.OVERLOADED: 503,
    RuntimeErrorType.INTERNAL: 500,
}
