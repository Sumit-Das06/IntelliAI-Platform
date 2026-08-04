"""HTTP-layer dependency providers.

Endpoints declare needs via ``Depends`` and annotated aliases; they never
import process-global state. Everything resolves from the current application
instance, so whatever the factory was given (production settings, test
settings) is what every endpoint sees.
"""

import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated, cast

import structlog
from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from intelliai_api.core.config import Settings
from intelliai_api.core.errors import AuthenticationError, RateLimitError
from intelliai_api.core.health import HealthService
from intelliai_api.limits import (
    AdmissionController,
    CapabilityAdmission,
    LimitRule,
    LimitScope,
    plan_for,
    refuse,
)
from intelliai_api.metering import (
    FileUsageFallback,
    NullUsageFallback,
    UsageFallback,
    UsageRecorder,
)
from intelliai_api.registry import Registry
from intelliai_api.runtimes import RuntimeClient
from intelliai_api.services.auth import AuthContext, AuthService
from intelliai_api.services.identity import IdentityService
from intelliai_api.services.speech import SpeechService
from intelliai_api.services.transcription import TranscriptionService


def app_settings(request: Request) -> Settings:
    """Settings of this application instance (factory-injected)."""
    # app.state is untyped by Starlette; the factory guarantees these types.
    return cast(Settings, request.app.state.settings)


def health_service(request: Request) -> HealthService:
    """Health service of this application instance (factory-injected)."""
    return cast(HealthService, request.app.state.health)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """One session — one unit of work — per request.

    Commit if the endpoint succeeds, roll back if it raises; either way the
    connection returns to the pool. Endpoints never manage transactions.
    """
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


SettingsDep = Annotated[Settings, Depends(app_settings)]
HealthDep = Annotated[HealthService, Depends(health_service)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _extract_bearer_credential(request: Request) -> str:
    """HTTP-layer concern: pull the credential out of the transport.

    Absence or a wrong scheme is ``missing_api_key`` — the caller didn't
    present a credential at all; nothing was verified and rejected.
    """
    header = request.headers.get("Authorization", "")
    scheme, _, credential = header.partition(" ")
    credential = credential.strip()
    if not header or scheme.lower() != "bearer" or not credential:
        raise AuthenticationError(
            "Provide an API key: 'Authorization: Bearer ik_live_...'.",
            code="missing_api_key",
        )
    return credential


async def current_auth(request: Request, session: SessionDep, settings: SettingsDep) -> AuthContext:
    """The authentication pipeline, as a composable dependency.

    Endpoints declare ``CurrentAuth`` and receive proof of identity;
    they never see the raw key. Successful auth binds org/key public ids
    into the logging context so every subsequent line carries them.
    """
    credential = _extract_bearer_credential(request)
    service = AuthService(session, pepper=settings.auth.key_pepper.get_secret_value())
    context = await service.authenticate(
        credential, request_id=getattr(request.state, "request_id", None)
    )
    # key_id, not api_key_id: the redaction processor masks "api_key" keys.
    # contextvars cover every log INSIDE the request task; request.state
    # carries the identity back across the BaseHTTPMiddleware task boundary
    # so the middleware's request_completed line gets it too.
    structlog.contextvars.bind_contextvars(
        organization_id=context.organization_public_id,
        key_id=context.key_public_id,
    )
    request.state.organization_id = context.organization_public_id
    request.state.key_id = context.key_public_id
    return context


def identity_service(session: SessionDep, settings: SettingsDep) -> IdentityService:
    """Business-capability dependency: routers stay thin, rules stay in services."""
    return IdentityService(session, pepper=settings.auth.key_pepper.get_secret_value())


def model_registry(request: Request) -> Registry:
    """The routing/product catalog of this application instance."""
    return cast(Registry, request.app.state.registry)


def admission_controller(request: Request) -> AdmissionController:
    """The limiter of this application instance (factory-built)."""
    return cast(AdmissionController, request.app.state.limits)


async def enforce_limits(
    request: Request,
    auth: Annotated[AuthContext, Depends(current_auth)],
    controller: Annotated[AdmissionController, Depends(admission_controller)],
    settings: SettingsDep,
) -> AsyncIterator[None]:
    """Admission control, attached to the ROUTER rather than to routes.

    This is what makes enforcement structural instead of procedural: a
    new endpoint under ``/v1`` cannot forget to be rate limited, because
    nobody has to remember. Adding a route inherits the guard; removing
    the guard is a one-line diff in the app factory that a test refuses.

    Identity-scoped only — organization ceiling, key subdivision, and the
    in-flight slot — because the body has not been parsed yet and the
    capability is not yet known. Capability-scoped limits run at the
    service seam, after registry resolution (§13.2).

    A generator dependency so the concurrency slot is released on the way
    out no matter how the request ends, including when it raises.
    """
    plan = plan_for(auth.organization.plan)
    control_plane = _is_control_plane(request)
    scope = LimitScope.CONTROL_PLANE if control_plane else LimitScope.ORGANIZATION
    surface = scope.value
    allowance = (
        plan.control_plane_requests_per_minute if control_plane else plan.requests_per_minute
    )
    rules = [
        LimitRule(
            scope=scope,
            identity=auth.organization_public_id,
            requests_per_minute=allowance,
            burst=plan.burst,
        ),
        # A subdivision of the organization's allowance, never an
        # addition: keys are unlimited in number and free to create, so a
        # per-key limit without an org ceiling above it is defeated by
        # making more keys.
        #
        # Namespaced by SURFACE, so the two budgets are separate all the
        # way down. A shared key bucket would quietly re-open the hole the
        # control-plane bucket exists to close: enumeration consuming the
        # inference allowance a customer paid for.
        LimitRule(
            scope=LimitScope.API_KEY,
            identity=f"{auth.key_public_id}:{surface}",
            requests_per_minute=allowance,
            burst=plan.burst,
        ),
    ]
    decision = await controller.check(rules)
    request.state.rate_limit = decision
    if not decision.allowed:
        raise refuse(decision)

    lease_key = f"concurrency:organization:{auth.organization_public_id}"
    lease_id = getattr(request.state, "request_id", None) or uuid.uuid4().hex
    acquired = await controller.acquire(
        lease_key,
        limit=plan.max_concurrent,
        lease_id=lease_id,
        ttl_ms=settings.limits.lease_seconds * 1000,
    )
    if not acquired:
        # Occupancy, not velocity — but still the caller's allowance, so
        # still a 429. Our own capacity exhaustion is the runtime's 503.
        raise RateLimitError(
            "Too many requests in flight for your organization. Retry when one completes.",
            code="rate_limit_exceeded",
            retry_after=1,
        )
    try:
        yield
    finally:
        await controller.release(lease_key, lease_id=lease_id)


def _is_control_plane(request: Request) -> bool:
    """Key and organization management get their own cheaper bucket.

    Not because they are expensive, but because credential enumeration
    lives here and should not be able to consume the inference
    allowance a customer paid for.
    """
    path = request.url.path
    return "/api-keys" in path or path.endswith("/organization")


def usage_recorder(request: Request, session: SessionDep, settings: SettingsDep) -> UsageRecorder:
    """The metering seam, wired to this request's own transaction.

    Successful events therefore commit with the response (§6 of the M4
    design). The session factory is handed over as well, because failure
    events must be written OUTSIDE this transaction — the request is
    about to roll it back, and the fact that we spent capacity is exactly
    what must survive that.
    """
    path = settings.metering.fallback_path
    fallback: UsageFallback = FileUsageFallback(Path(path)) if path else NullUsageFallback()
    return UsageRecorder(
        session,
        session_factory=cast("async_sessionmaker[AsyncSession]", request.app.state.session_factory),
        fallback=fallback,
    )


UsageDep = Annotated[UsageRecorder, Depends(usage_recorder)]


def idempotency_key(
    key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> str | None:
    """Optional client-supplied retry identity (ADR-0024).

    Additive and optional: callers that never send it are unaffected, and
    callers that do get at-most-once billing enforced by the ledger's
    uniqueness constraint.
    """
    return key


IdempotencyKey = Annotated[str | None, Depends(idempotency_key)]


def capability_admission(
    controller: Annotated[AdmissionController, Depends(admission_controller)],
) -> CapabilityAdmission:
    """The capability seam: services ask one question, know nothing of Redis."""
    return CapabilityAdmission(controller)


CapabilityAdmissionDep = Annotated[CapabilityAdmission, Depends(capability_admission)]


def transcription_service(
    request: Request, usage: UsageDep, admission: CapabilityAdmissionDep
) -> TranscriptionService:
    """Transcription flow: registry + runtime clients + metering + admission."""
    clients = cast(dict[str, RuntimeClient], request.app.state.runtime_clients)
    return TranscriptionService(
        cast(Registry, request.app.state.registry), clients, usage, admission
    )


def speech_service(
    request: Request, usage: UsageDep, admission: CapabilityAdmissionDep
) -> SpeechService:
    """Synthesis flow: registry + voices + runtime clients + metering + admission."""
    clients = cast(dict[str, RuntimeClient], request.app.state.runtime_clients)
    return SpeechService(cast(Registry, request.app.state.registry), clients, usage, admission)


CurrentAuth = Annotated[AuthContext, Depends(current_auth)]
IdentityDep = Annotated[IdentityService, Depends(identity_service)]
RegistryDep = Annotated[Registry, Depends(model_registry)]
TranscriptionDep = Annotated[TranscriptionService, Depends(transcription_service)]
SpeechDep = Annotated[SpeechService, Depends(speech_service)]
