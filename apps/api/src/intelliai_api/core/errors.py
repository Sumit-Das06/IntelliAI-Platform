"""Platform error taxonomy — the error contract, independent of HTTP.

Every failure the platform can produce maps to one of the ``ErrorType``
classifications below and is rendered by the HTTP layer into the single
platform envelope:

    {"error": {"type": "rate_limit_error", "code": "rate_limit_exceeded",
               "message": "…", "param": null, "request_id": "req_…"}}

Contract semantics (stable forever once shipped):

- ``type``  — coarse classification. SDKs map these to exception classes
  and retry policy. The set may GROW; existing members never change meaning.
- ``code``  — fine-grained machine condition (``audio_too_long``,
  ``voice_not_found``). New codes are always additive and non-breaking.
- ``param`` — the offending request field, when one is identifiable.
- ``message`` — human-readable; NEVER stable API; clients must not parse it.

Retryability is part of the contract:

- Retryable (after backoff, honoring ``Retry-After`` when present):
  ``rate_limit_error``, ``service_unavailable_error``, and ``internal_error``
  (once, cautiously — the request was valid; the platform failed).
- Never retryable: every other 4xx — the request itself is wrong, and
  identical retries will fail identically forever.
"""

from enum import StrEnum


class ErrorType(StrEnum):
    INVALID_REQUEST = "invalid_request_error"
    AUTHENTICATION = "authentication_error"
    AUTHORIZATION = "authorization_error"
    NOT_FOUND = "resource_not_found_error"
    CONFLICT = "conflict_error"
    RATE_LIMIT = "rate_limit_error"
    QUOTA_EXCEEDED = "quota_exceeded_error"
    INTERNAL = "internal_error"
    SERVICE_UNAVAILABLE = "service_unavailable_error"


RETRYABLE_TYPES = frozenset(
    {ErrorType.RATE_LIMIT, ErrorType.SERVICE_UNAVAILABLE, ErrorType.INTERNAL}
)


class IntelliAIError(Exception):
    """Base of every deliberately-raised platform error.

    Subclasses pin ``error_type`` and ``status_code``; call sites supply the
    human message and, where useful, a machine ``code`` and ``param``.
    """

    error_type: ErrorType = ErrorType.INTERNAL
    status_code: int = 500

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        param: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.param = param

    @property
    def retryable(self) -> bool:
        return self.error_type in RETRYABLE_TYPES


class InvalidRequestError(IntelliAIError):
    error_type = ErrorType.INVALID_REQUEST
    status_code = 400


class AuthenticationError(IntelliAIError):
    error_type = ErrorType.AUTHENTICATION
    status_code = 401


class AuthorizationError(IntelliAIError):
    error_type = ErrorType.AUTHORIZATION
    status_code = 403


class ResourceNotFoundError(IntelliAIError):
    error_type = ErrorType.NOT_FOUND
    status_code = 404


class ConflictError(IntelliAIError):
    error_type = ErrorType.CONFLICT
    status_code = 409


class RateLimitError(IntelliAIError):
    error_type = ErrorType.RATE_LIMIT
    status_code = 429

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        param: str | None = None,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(message, code=code, param=param)
        self.retry_after = retry_after


class QuotaExceededError(IntelliAIError):
    """Distinct from rate limiting: backoff will not help; buying capacity will."""

    error_type = ErrorType.QUOTA_EXCEEDED
    status_code = 429


class InternalError(IntelliAIError):
    error_type = ErrorType.INTERNAL
    status_code = 500


class ServiceUnavailableError(IntelliAIError):
    error_type = ErrorType.SERVICE_UNAVAILABLE
    status_code = 503

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        param: str | None = None,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(message, code=code, param=param)
        self.retry_after = retry_after
