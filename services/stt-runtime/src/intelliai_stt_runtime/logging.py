"""Structured event logging — the platform standard, runtime edition.

Same principles as the gateway (events not prose; one pipeline, two
renderings; automatic service context; key-based redaction), trimmed to
what a runtime needs. Collectors read stdout; the process never knows
where logs go.
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict

from intelliai_stt_runtime import __version__
from intelliai_stt_runtime.config import Settings
from intelliai_stt_runtime.identity import SERVICE_NAME

_SENSITIVE_KEY_MARKERS = (
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
)


def _redact(_: Any, __: str, event_dict: EventDict) -> EventDict:
    for key in event_dict:
        lowered = key.lower()
        if any(marker in lowered for marker in _SENSITIVE_KEY_MARKERS):
            event_dict[key] = "[REDACTED]"
    return event_dict


def _service_context(_: Any, __: str, event_dict: EventDict) -> EventDict:
    event_dict.setdefault("service", SERVICE_NAME)
    event_dict.setdefault("service_version", __version__)
    return event_dict


def configure_logging(settings: Settings) -> None:
    shared: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
        _service_context,
        _redact,
    ]
    renderer: structlog.types.Processor
    if settings.console_logs:
        renderer = structlog.dev.ConsoleRenderer()
        tail: list[structlog.types.Processor] = [renderer]
    else:
        renderer = structlog.processors.JSONRenderer()
        tail = [structlog.processors.format_exc_info, renderer]

    structlog.configure(
        processors=[*shared, *tail],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, settings.log_level)),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=False,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
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
    access = logging.getLogger("uvicorn.access")
    access.handlers.clear()
    access.propagate = False
