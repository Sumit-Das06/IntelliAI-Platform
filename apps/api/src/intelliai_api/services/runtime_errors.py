"""Runtime taxonomy -> public taxonomy, totally (every type mapped).

One translation for every capability service (extracted at the second
consumer, M3 step 5): invalid_input messages are written wire-safe by the
runtime and customer-actionable, so they pass through; capacity states
collapse to the public service_unavailable with retry guidance; internals
stay opaque — details live in runtime logs, correlated by request id.
"""

from intelliai_api.core.errors import (
    IntelliAIError,
    InternalError,
    InvalidRequestError,
    ServiceUnavailableError,
)
from intelliai_runtime_contract import RuntimeErrorType


def translate_runtime_error(
    error_type: RuntimeErrorType, message: str, param: str | None
) -> IntelliAIError:
    if error_type is RuntimeErrorType.INVALID_INPUT:
        return InvalidRequestError(message, param=param)
    if error_type is RuntimeErrorType.NOT_READY:
        return ServiceUnavailableError(
            "The model is starting up. Retry shortly.", code="model_loading", retry_after=2
        )
    if error_type is RuntimeErrorType.OVERLOADED:
        return ServiceUnavailableError(
            "The service is at capacity. Retry shortly.", code="overloaded", retry_after=1
        )
    return InternalError("The service encountered an internal error.")
