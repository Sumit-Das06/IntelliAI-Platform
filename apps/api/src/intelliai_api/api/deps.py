"""HTTP-layer dependency providers.

Endpoints declare needs via ``Depends`` and annotated aliases; they never
import process-global state. Everything resolves from the current application
instance, so whatever the factory was given (production settings, test
settings) is what every endpoint sees.
"""

from typing import Annotated

from fastapi import Depends, Request

from intelliai_api.core.config import Settings
from intelliai_api.core.health import HealthService


def app_settings(request: Request) -> Settings:
    """Settings of this application instance (factory-injected)."""
    return request.app.state.settings


def health_service(request: Request) -> HealthService:
    """Health service of this application instance (factory-injected)."""
    return request.app.state.health


SettingsDep = Annotated[Settings, Depends(app_settings)]
HealthDep = Annotated[HealthService, Depends(health_service)]
