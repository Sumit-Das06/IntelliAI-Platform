"""HTTP-layer dependency providers.

Endpoints declare needs via ``Depends`` and annotated aliases; they never
import process-global state. Everything resolves from the current application
instance, so whatever the factory was given (production settings, test
settings) is what every endpoint sees.
"""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from intelliai_api.core.config import Settings
from intelliai_api.core.health import HealthService


def app_settings(request: Request) -> Settings:
    """Settings of this application instance (factory-injected)."""
    return request.app.state.settings


def health_service(request: Request) -> HealthService:
    """Health service of this application instance (factory-injected)."""
    return request.app.state.health


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
