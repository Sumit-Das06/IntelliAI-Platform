"""The unauthenticated edge: the only protection that exists before identity.

A flood of invalid keys costs us an HMAC and an indexed database lookup
each (ADR-0012). Without a guard *before* authentication, an attacker
makes us do unbounded work for free, and no per-organization limit can
help because there is no organization yet.

This is the one and only place IP is a legitimate dimension. After
authentication it becomes a bad one — NAT, cloud egress, and shared
proxies make it both unfair and trivially evaded — which is why level 0
of the §10.2 hierarchy is scoped to "pre-auth only" rather than being a
general-purpose limiter.

Deliberately says nothing: an unauthenticated caller learns only that
they were refused. Rate-limit headers and scope details are help for a
customer, not intelligence for a scanner.
"""

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from intelliai_api.core.errors import ErrorType
from intelliai_api.limits import (
    UNAUTHENTICATED_BURST,
    UNAUTHENTICATED_REQUESTS_PER_MINUTE,
    AdmissionController,
    LimitRule,
    LimitScope,
)

logger = structlog.get_logger("intelliai_api.edge")

# Probes must never be rate limited: an orchestrator that cannot read
# liveness will restart a healthy process, turning a protection mechanism
# into an outage.
_EXEMPT_PREFIXES = ("/health",)


class UnauthenticatedEdgeMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, controller: AdmissionController) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._controller = controller

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path.startswith(_EXEMPT_PREFIXES) or not self._controller.enabled:
            return await call_next(request)

        client = request.client
        if client is None:  # no peer address (in-process transport, unix socket)
            return await call_next(request)

        decision = await self._controller.check(
            [
                LimitRule(
                    scope=LimitScope.IP,
                    identity=client.host,
                    requests_per_minute=UNAUTHENTICATED_REQUESTS_PER_MINUTE,
                    burst=UNAUTHENTICATED_BURST,
                )
            ]
        )
        if decision.allowed:
            return await call_next(request)

        logger.warning("edge.rate_limited", client_ip=client.host)
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(decision.retry_after or 1)},
            content={
                "error": {
                    "type": ErrorType.RATE_LIMIT.value,
                    "code": "rate_limit_exceeded",
                    "message": "Too many requests. Slow down and retry shortly.",
                    "param": None,
                    "request_id": getattr(request.state, "request_id", None),
                }
            },
        )
