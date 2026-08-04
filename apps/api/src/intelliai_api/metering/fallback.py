"""The durable sink of last resort: where a rejected ledger write goes.

If the database refuses a usage event, the customer still receives their
response (§6 of the M4 design). That decision is only defensible if the
fact survives somewhere the database is not — otherwise "degrade open"
quietly means "lose the revenue".

Two sinks, independent on purpose, because they fail for different
reasons:

- the **CRITICAL log line** the recorder always emits — structured,
  complete enough to replay the event, and shipped off-host, so it
  survives losing the machine;
- the **append-only file** here — local, synchronous, and unaffected by
  a log pipeline outage, so it survives losing the log path.

Neither is a queue and neither claims to be. They are the evidence that
lets a human reconstruct what the ledger missed, and their existence is
what the daily reconciliation invariant checks against.
"""

import json
from pathlib import Path
from typing import Any, Protocol

import structlog

logger = structlog.get_logger(__name__)


class UsageFallback(Protocol):
    """Capture a usage event the ledger refused. Must never raise."""

    def capture(self, payload: dict[str, Any]) -> None: ...


class NullUsageFallback:
    """No local sink — the CRITICAL log line is the only record.

    The correct choice where logs are reliably shipped and the local
    filesystem is not durable anyway (most container deployments).
    """

    def capture(self, payload: dict[str, Any]) -> None:
        return None


class FileUsageFallback:
    """Append the rejected event to a JSONL file, synchronously.

    Synchronous on purpose: an asynchronous write that is still buffered
    when the process dies would provide the appearance of durability
    without the fact of it.
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    def capture(self, payload: dict[str, Any]) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as sink:
                sink.write(json.dumps(payload, default=str, sort_keys=True) + "\n")
        except Exception:
            # The sink of last resort has no sink of its own. Losing the
            # file must still not cost the customer their response.
            logger.critical("usage.fallback_write_failed", path=str(self._path))
