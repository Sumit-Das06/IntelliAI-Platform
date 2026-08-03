"""HTTP binding constants for the binary audio binding (ADR-0020).

Deliberately OUTSIDE packages/runtime-contract: the contract is
transport-free; the binding belongs to the services that speak HTTP. The
gateway's client pins the same names with a cross-checked test (M3 step 5).

The binding: JSON ``SpeechSynthesisRequest`` in, raw WAV bytes out, the
success envelope JSON-serialized into ``X-Runtime-Envelope``. Errors are
ALWAYS JSON with these statuses — one error shape platform-wide, never
binary. The envelope header is operational metadata only and its size
ceiling is a binding constant pinned by test: well under common proxy
header limits (~8 KB total is a typical default), so infrastructure never
accidentally truncates it. Anything that wants to be large belongs in the
body or in logs — never in the envelope.

Statuses here are the INTERNAL binding, never the public API: the gateway
re-maps runtime errors into the public envelope (ADR-0009).
"""

from typing import Final

from intelliai_runtime_contract import RuntimeErrorType

HEADER_REQUEST_ID: Final = "X-Request-ID"
HEADER_CONTRACT_VERSION: Final = "X-Runtime-Contract-Version"
HEADER_RUNTIME_ENVELOPE: Final = "X-Runtime-Envelope"

# The pinned ceiling (ADR-0020 invariant 2). Operational metadata is
# bounded by construction; this number makes the bound a tested fact.
MAX_ENVELOPE_HEADER_BYTES: Final = 4096

ROUTE_SYNTHESIZE: Final = "/v1/synthesize"
MEDIA_TYPE_WAV: Final = "audio/wav"

STATUS_BY_ERROR_TYPE: Final[dict[RuntimeErrorType, int]] = {
    RuntimeErrorType.INVALID_INPUT: 400,
    RuntimeErrorType.NOT_READY: 503,
    RuntimeErrorType.OVERLOADED: 503,
    RuntimeErrorType.INTERNAL: 500,
}
