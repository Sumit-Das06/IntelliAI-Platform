"""API key management endpoints — thin by law: parse → service → shape.

The one place in the entire API surface where a plaintext key appears:
the ``key`` field of the CREATE response. Every other representation of a
key is metadata. That asymmetry is the product's security model.
"""

from datetime import datetime

from fastapi import APIRouter, status
from pydantic import AwareDatetime, BaseModel, Field

from intelliai_api.api.deps import CurrentAuth, IdentityDep
from intelliai_api.db.models import ApiKey

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


class CreateApiKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    expires_at: AwareDatetime | None = None  # timezone-aware or rejected


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    key_last4: str
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None


class ApiKeyCreatedResponse(ApiKeyResponse):
    # Plaintext, shown exactly once. Store it; it is never retrievable.
    key: str


class ApiKeyListResponse(BaseModel):
    # Envelope (not a bare array) so pagination fields can arrive additively.
    data: list[ApiKeyResponse]


def _to_response(api_key: ApiKey) -> ApiKeyResponse:
    return ApiKeyResponse(
        id=api_key.public_id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        key_last4=api_key.key_last4,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        expires_at=api_key.expires_at,
        revoked_at=api_key.revoked_at,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: CreateApiKeyRequest, auth: CurrentAuth, identity: IdentityDep
) -> ApiKeyCreatedResponse:
    """Mint a key for the authenticated organization. The response's ``key``
    field is the only time the secret will ever be shown."""
    api_key, generated = await identity.create_key(auth, name=body.name, expires_at=body.expires_at)
    return ApiKeyCreatedResponse(**_to_response(api_key).model_dump(), key=generated.secret)


@router.get("")
async def list_api_keys(auth: CurrentAuth, identity: IdentityDep) -> ApiKeyListResponse:
    """All of the organization's keys — metadata only, secrets don't exist."""
    keys = await identity.list_keys(auth)
    return ApiKeyListResponse(data=[_to_response(key) for key in keys])


@router.post("/{key_id}/revoke")
async def revoke_api_key(key_id: str, auth: CurrentAuth, identity: IdentityDep) -> ApiKeyResponse:
    """Soft-revoke: effective on the key's next authentication attempt.
    Idempotent — revoking a revoked key returns it unchanged (200)."""
    return _to_response(await identity.revoke_key(auth, key_id))
