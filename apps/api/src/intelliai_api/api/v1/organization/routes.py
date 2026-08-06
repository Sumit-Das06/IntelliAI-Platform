"""Organization endpoints — thin by law: parse → context → shape."""

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from intelliai_api.api.deps import CurrentAuth

router = APIRouter(prefix="/organization", tags=["organization"])


class OrganizationResponse(BaseModel):
    id: str  # public_id — internal integers never cross the API boundary
    name: str
    created_at: datetime
    # Whether this tenant has opted in to speech data collection. Exposed
    # so clients can show an honest consent state (the playground's
    # notice, the future console's settings page) without a second call.
    data_consent: bool
    data_consented_at: datetime | None


@router.get("")
async def get_organization(auth: CurrentAuth) -> OrganizationResponse:
    """Who am I? The authenticated caller's own organization."""
    organization = auth.organization
    return OrganizationResponse(
        id=organization.public_id,
        name=organization.name,
        created_at=organization.created_at,
        data_consent=organization.data_consent,
        data_consented_at=organization.data_consented_at,
    )
