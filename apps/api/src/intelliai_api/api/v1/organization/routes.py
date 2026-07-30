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


@router.get("")
async def get_organization(auth: CurrentAuth) -> OrganizationResponse:
    """Who am I? The authenticated caller's own organization."""
    organization = auth.organization
    return OrganizationResponse(
        id=organization.public_id,
        name=organization.name,
        created_at=organization.created_at,
    )
