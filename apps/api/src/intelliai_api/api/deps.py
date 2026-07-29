"""HTTP-layer dependency providers.

Endpoints declare needs via ``Depends`` and annotated aliases; they never
import process-global state. Everything resolves from the current application
instance, so whatever the factory was given (production settings, test
settings) is what every endpoint sees.
"""

from typing import Annotated

from fastapi import Depends, Request

from intelliai_api.core.config import Settings


def app_settings(request: Request) -> Settings:
    """Settings of this application instance (factory-injected)."""
    return request.app.state.settings


SettingsDep = Annotated[Settings, Depends(app_settings)]
