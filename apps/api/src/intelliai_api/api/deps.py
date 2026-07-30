"""HTTP-layer dependency providers.

Endpoints declare needs via ``Depends`` and annotated aliases; they never
import process-global state. Everything resolves from the current application
instance, so whatever the factory was given (production settings, test
settings) is what every endpoint sees.
"""

from collections.abc import AsyncIterator
from typing import Annotated, cast

import structlog
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from intelliai_api.core.config import Settings
from intelliai_api.core.errors import AuthenticationError
from intelliai_api.core.health import HealthService
from intelliai_api.services.auth import AuthContext, AuthService
from intelliai_api.services.identity import IdentityService


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


CurrentAuth = Annotated[AuthContext, Depends(current_auth)]
IdentityDep = Annotated[IdentityService, Depends(identity_service)]
