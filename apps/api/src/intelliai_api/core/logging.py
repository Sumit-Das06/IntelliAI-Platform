"""Structured, event-based logging for the platform.

Principles (see PRD §9 and the logging ADR, M0.5):

- Log entries are events with metadata, never prose: ``event="request_completed"``
  plus fields, not "Request finished successfully.". Event names are stable
  API for dashboards and alerts; details ride in the metadata.
- One code path, two renderings: pretty console output in dev, JSON lines on
  stdout everywhere else. Collectors (Loki, CloudWatch, …) consume stdout;
  the application never knows where logs go.
- Every entry automatically carries the platform-standard fields: timestamp,
  level, event, service, service_version, environment — plus anything bound
  to the request context (request_id today; org_id/user_id/api_key_id when
  auth lands; model_id/provider when inference lands).
- Sensitive keys are redacted by a processor as defense-in-depth behind
  ``SecretStr``. Logging a credential by accident must be hard.
"""

import logging
import sys
from typing import Any

import structlog

from intelliai_api import __version__
from intelliai_api.core.config import Settings

SERVICE_NAME = "intelliai-api"

REDACTED = "[REDACTED]"
_SENSITIVE_KEY_MARKERS = (
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "set-cookie",
)

_EventDict = dict[str, Any]


def redact_sensitive(_: Any, __: str, event_dict: _EventDict) -> _EventDict:
    """Replace the value of any credential-looking key with ``[REDACTED]``.

    Matches on key *names* (``password``, ``api_key``, ``authorization`` …),
    so redaction cannot be forgotten at call sites — it applies to every
    entry from every logger, including third-party ones routed through the
    stdlib bridge.
    """
    for key in event_dict:
        lowered = key.lower()
        if any(marker in lowered for marker in _SENSITIVE_KEY_MARKERS):
            event_dict[key] = REDACTED
    return event_dict


def _service_context(environment: str) -> structlog.types.Processor:
    def processor(_: Any, __: str, event_dict: _EventDict) -> _EventDict:
        event_dict.setdefault("service", SERVICE_NAME)
        event_dict.setdefault("service_version", __version__)
        event_dict.setdefault("environment", environment)
        return event_dict

    return processor


def configure_logging(settings: Settings) -> None:
    """Configure structlog and the stdlib bridge for this process.

    Idempotent and cheap; called from ``create_app``. Logging configuration
    is inherently process-global — the one exception to our "no global state"
    rule, accepted because log routing is an operational concern, not
    application state.
    """
    dev_console = settings.is_dev

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
        _service_context(settings.env.value),
        redact_sensitive,
    ]

    if dev_console:
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer()
        tail: list[structlog.types.Processor] = [renderer]
    else:
        renderer = structlog.processors.JSONRenderer()
        tail = [
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ]

    structlog.configure(
        processors=[*shared_processors, *tail],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level)
        ),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,
    )

    # Route stdlib records (uvicorn, libraries, alembic) through the same
    # pipeline so every line in the process renders identically.
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level)

    for name in ("uvicorn", "uvicorn.error"):
        server_logger = logging.getLogger(name)
        server_logger.handlers.clear()
        server_logger.propagate = True
    # Our middleware emits request_started/request_completed; uvicorn's own
    # access log would duplicate every line.
    access = logging.getLogger("uvicorn.access")
    access.handlers.clear()
    access.propagate = False
