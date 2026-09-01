"""POST /v1/text/corrections — Smart Transcript Correction (M57).

The POST-FINAL, user-triggered correction action: the browser (or any
authenticated API caller) sends the displayed transcript, the runtime's
flag-gated correction stage answers with the improved text. STAGING
ONLY — production deployments run with the runtime flag off, so this
endpoint answers a friendly unavailable there.

Laws carried here:

* auth first — same key contexts as every /v1 endpoint; the raw
  llama-server is never exposed to a browser (Phase 34).
* fail-open — a correction failure NEVER damages a transcript; the
  caller keeps what it has and shows a friendly state (Phase 32).
* provenance — when the caller names a collected sample, the suggestion
  is recorded as its own `ai_correction_suggested` lifecycle event,
  DISTINCT from the human `corrected` event (Phases 7/18/36); recording
  failure never fails the correction itself.
* privacy — transcript text goes to the local runtime only; it is never
  logged here and never leaves the deployment (Phase 35).
"""

from __future__ import annotations

import contextlib

import httpx
import structlog
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from intelliai_api.api.deps import CollectionDep, CurrentAuth
from intelliai_api.core.errors import InvalidRequestError, ServiceUnavailableError

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/text", tags=["text"])

_RUNTIME_ROUTE = "/v1/correct"
_TIMEOUT_SECONDS = 90.0


class SmartCorrectionRequest(BaseModel):
    """Bounded like the human-correction endpoint: 20k chars refuses
    only abuse; the runtime applies its own word ceiling."""

    text: str = Field(min_length=1, max_length=20_000)
    language: str = Field(min_length=2, max_length=8)
    #: Optional: a collected sample this transcript belongs to — records
    #: the suggestion in that sample's lifecycle history.
    sample_id: str | None = None


class SmartCorrectionResponse(BaseModel):
    corrected_text: str


def _unavailable() -> ServiceUnavailableError:
    return ServiceUnavailableError(
        "AI correction is not available right now. Your transcript is unaffected.",
        code="smart_correction_unavailable",
        retry_after=5,
    )


@router.post("/corrections")
async def smart_correct(
    body: SmartCorrectionRequest,
    auth: CurrentAuth,
    request: Request,
    collection: CollectionDep,
) -> SmartCorrectionResponse:
    settings = request.app.state.settings
    base_url = settings.runtimes.stt_url
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=_TIMEOUT_SECONDS) as client:
            response = await client.post(
                _RUNTIME_ROUTE, json={"text": body.text, "language": body.language}
            )
    except httpx.HTTPError as exc:
        logger.info("smart_correction_runtime_unreachable", detail=type(exc).__name__)
        raise _unavailable() from exc

    if response.status_code == 400:
        # The runtime writes invalid_input messages wire-safe and
        # customer-actionable (the M16 law) — pass the message through.
        message = "The transcript could not be corrected."
        with contextlib.suppress(ValueError):
            message = str(response.json().get("message") or message)
        raise InvalidRequestError(message, param="text")
    if response.status_code != 200:
        logger.info("smart_correction_refused", status=response.status_code)
        raise _unavailable()

    try:
        corrected = str(response.json()["corrected_text"])
    except (ValueError, KeyError) as exc:
        logger.info("smart_correction_envelope_malformed")
        raise _unavailable() from exc

    if body.sample_id:
        # Provenance, best-effort: the suggestion joins the sample's
        # append-only history; a recording problem must never fail the
        # correction the user is looking at.
        try:
            await collection.record_ai_suggestion(
                auth=auth, sample_public_id=body.sample_id, suggested_text=corrected
            )
        except Exception:
            logger.info("smart_correction_suggestion_not_recorded")

    logger.info(
        "smart_correction_served",
        organization_id=auth.organization_public_id,
        language=body.language,
        input_chars=len(body.text),
        output_chars=len(corrected),
    )
    return SmartCorrectionResponse(corrected_text=corrected)
