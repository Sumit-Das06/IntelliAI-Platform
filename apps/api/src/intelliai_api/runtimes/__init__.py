"""Runtime clients — how the gateway speaks the runtime contract.

Module charter:

1. **Why it exists** — one seam between the gateway and every inference
   runtime. Routers and services depend on the `RuntimeClient` Protocol;
   HOW a runtime is reached (HTTP today; gRPC or in-process later) is an
   implementation detail swapped here with zero changes above (M2
   refinement 6, ADR-0016).
2. **What it owns** — the transport-agnostic Protocol, typed failure
   surface (`RuntimeCallError`, `RuntimeUnavailableError`), and transport
   implementations (HTTP today).
3. **What it must never own** — routing decisions (registry's), error
   *translation* to the public contract (TranscriptionService's), retries
   and accounting (gateway policy layers), engine or model knowledge.
4. **Who may import it** — gateway services and the app factory. Never
   routers directly (they go through services).
5. **What it may import** — the runtime contract, httpx, core errors.
   Never a runtime service's package (production code; the binding
   cross-pin TEST imports one, deliberately, as CI enforcement).
6. **How it grows** — new transports implement the same Protocol; M8
   streaming ADDS a method (additive Protocol evolution, same rule as the
   contract) rather than changing `transcribe`.
"""

from intelliai_api.runtimes.client import (
    RuntimeCallError,
    RuntimeClient,
    RuntimeUnavailableError,
)
from intelliai_api.runtimes.http import HTTPRuntimeClient

__all__ = [
    "HTTPRuntimeClient",
    "RuntimeCallError",
    "RuntimeClient",
    "RuntimeUnavailableError",
]
