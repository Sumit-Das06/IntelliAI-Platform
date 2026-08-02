"""The runtime's one failure exception, carrying contract vocabulary.

Any layer (manager, pipeline, pool, engines) raises ``RuntimeServiceError`` with
a ``RuntimeErrorType``; only the HTTP binding turns it into a response.
Nothing here knows transport — the taxonomy stays contract-shaped
(ADR-0016)."""

from intelliai_runtime_contract import RuntimeErrorType


class RuntimeServiceError(Exception):
    def __init__(
        self,
        error_type: RuntimeErrorType,
        message: str,
        *,
        param: str | None = None,
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.message = message
        self.param = param
