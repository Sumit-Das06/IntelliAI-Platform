"""TranscriptionService — the gateway's half of the transcription flow.

Owns exactly what ADR-0016 assigns the gateway: registry resolution,
runtime invocation through the client seam, TOTAL translation of runtime
failures into the public error contract (ADR-0009), and the platform
accounting event. Customers never learn which runtime, engine, or
foundation model served them — the public surface speaks public model
names and the public taxonomy, nothing else.
"""

from collections.abc import Mapping
from dataclasses import dataclass

import structlog

from intelliai_api.core.errors import (
    InternalError,
    InvalidRequestError,
    ServiceUnavailableError,
)
from intelliai_api.registry import Registry
from intelliai_api.runtimes import RuntimeCallError, RuntimeClient, RuntimeUnavailableError
from intelliai_api.services.auth import AuthContext
from intelliai_api.services.runtime_errors import translate_runtime_error
from intelliai_runtime_contract import (
    Capability,
    TranscriptionRequest,
    TranscriptionResult,
    UsageUnit,
)

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class TranscriptionOutcome:
    """What the route renders: the result plus its accounting facts."""

    result: TranscriptionResult
    public_model_id: str
    audio_seconds: float


class TranscriptionService:
    def __init__(self, registry: Registry, clients: Mapping[str, RuntimeClient]) -> None:
        self._registry = registry
        self._clients = clients

    async def transcribe(
        self,
        *,
        auth: AuthContext,
        public_model_id: str,
        audio: bytes,
        language: str | None,
    ) -> TranscriptionOutcome:
        resolution = self._registry.resolve(public_model_id)  # unknown -> 404 model_not_found
        if resolution.capability is not Capability.TRANSCRIPTION:
            raise InvalidRequestError(
                f"The model {public_model_id!r} does not support audio transcription.",
                param="model",
                code="capability_mismatch",
            )
        client = self._clients.get(resolution.service)
        if client is None:
            # Registry routes to a service this deployment never configured:
            # an operations problem, never the customer's.
            logger.error("runtime_client_missing", service=resolution.service)
            raise InternalError("The service is misconfigured.")

        try:
            envelope = await client.transcribe(
                audio,
                TranscriptionRequest(language=language, model=resolution.artifact.id),
            )
        except RuntimeCallError as exc:
            raise translate_runtime_error(
                exc.error.type, exc.error.message, exc.error.param
            ) from exc
        except RuntimeUnavailableError as exc:
            raise ServiceUnavailableError(
                "Transcription is temporarily unavailable. Retry shortly.",
                code="runtime_unavailable",
                retry_after=1,
            ) from exc

        audio_seconds = sum(
            usage.amount for usage in envelope.usage if usage.unit is UsageUnit.AUDIO_SECONDS
        )
        # The platform accounting event (M2 refinement 7): billing, usage
        # dashboards, and analytics consume THIS, emitted only by the
        # gateway, in public vocabulary (public model id, org id).
        logger.info(
            "transcription.completed",
            organization_id=auth.organization_public_id,
            model=public_model_id,
            audio_seconds=round(audio_seconds, 3),
            language=envelope.output.language,
        )
        return TranscriptionOutcome(
            result=envelope.output,
            public_model_id=public_model_id,
            audio_seconds=audio_seconds,
        )
