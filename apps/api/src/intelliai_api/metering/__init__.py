"""Metering: turning served requests into permanent commercial facts.

The control plane's half of the commercial boundary. Nothing here knows
what an engine is, and nothing in the inference plane knows this package
exists — the runtimes report measurements through the contract and are
finished.

The public seam is ``UsageRecorder`` (ADR-0021): it takes what the
gateway already knows about a completed request and writes exactly one
ledger row. It is deliberately impossible to make it raise on the serving
path — *serving degrades open, accounting degrades loud*.
"""

from intelliai_api.metering.fallback import (
    FileUsageFallback,
    NullUsageFallback,
    UsageFallback,
)
from intelliai_api.metering.lineage import runtime_lineage
from intelliai_api.metering.recorder import UsageRecorder

__all__ = [
    "FileUsageFallback",
    "NullUsageFallback",
    "UsageFallback",
    "UsageRecorder",
    "runtime_lineage",
]
