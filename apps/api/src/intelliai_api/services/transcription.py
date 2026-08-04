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
from decimal import Decimal

import structlog

from intelliai_api.core.errors import (
    InternalError,
    InvalidRequestError,
    ServiceUnavailableError,
)
from intelliai_api.limits import CapabilityAdmission
from intelliai_api.metering import UsageRecorder, runtime_lineage
from intelliai_api.registry import Registry, Resolution
from intelliai_api.runtimes import RuntimeCallError, RuntimeClient, RuntimeUnavailableError
from intelliai_api.services.auth import AuthContext
from intelliai_api.services.runtime_errors import translate_runtime_error
from intelliai_runtime_contract import (
    Capability,
    RuntimeErrorType,
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
    def __init__(
        self,
        registry: Registry,
        clients: Mapping[str, RuntimeClient],
        usage: UsageRecorder | None = None,
        admission: CapabilityAdmission | None = None,
    ) -> None:
        self._registry = registry
        self._clients = clients
        self._usage = usage
        self._admission = admission

    async def transcribe(
        self,
        *,
        auth: AuthContext,
        public_model_id: str,
        audio: bytes,
        language: str | None,
        idempotency_key: str | None = None,
    ) -> TranscriptionOutcome:
        resolution = self._registry.resolve(public_model_id)  # unknown -> 404 model_not_found
        if resolution.capability is not Capability.TRANSCRIPTION:
            raise InvalidRequestError(
                f"The model {public_model_id!r} does not support audio transcription.",
                param="model",
                code="capability_mismatch",
            )
        # Capability-scoped admission: only knowable HERE, after the
        # registry says what this request actually is. STT and TTS have
        # capacity profiles an order of magnitude apart, so they get
        # separate budgets rather than one shared request count.
        if self._admission is not None:
            await self._admission.check_capability(
                organization_id=auth.organization_public_id,
                plan_id=auth.organization.plan,
                capability=Capability.TRANSCRIPTION.value,
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
            await self._record_failure(auth, resolution, language, exc.error.type)
            raise translate_runtime_error(
                exc.error.type, exc.error.message, exc.error.param
            ) from exc
        except RuntimeUnavailableError as exc:
            await self._record_failure(auth, resolution, language, None)
            raise ServiceUnavailableError(
                "Transcription is temporarily unavailable. Retry shortly.",
                code="runtime_unavailable",
                retry_after=1,
            ) from exc

        audio_seconds = sum(
            usage.amount for usage in envelope.usage if usage.unit is UsageUnit.AUDIO_SECONDS
        )
        # The permanent commercial fact (ADR-0021), written before the
        # response is serialized, inside this request's own transaction.
        # The language recorded is the one OBSERVED (detected or honored),
        # not the one requested — the ledger stores facts.
        if self._usage is not None:
            await self._usage.record_success(
                auth=auth,
                capability=Capability.TRANSCRIPTION.value,
                public_model_id=public_model_id,
                quantities={UsageUnit.AUDIO_SECONDS.value: Decimal(str(audio_seconds))},
                language=envelope.output.language,
                lineage=runtime_lineage(
                    resolution,
                    served_artifact=envelope.model,
                    service_version=envelope.runtime.service_version,
                ),
                idempotency_key=idempotency_key,
            )
        # The request-event side of the daily reconciliation invariant:
        # successful billable responses must equal billable ledger rows.
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

    async def _record_failure(
        self,
        auth: AuthContext,
        resolution: Resolution,
        language: str | None,
        error_type: RuntimeErrorType | None,
    ) -> None:
        if self._usage is None:
            return
        await self._usage.record_runtime_failure(
            auth=auth,
            capability=Capability.TRANSCRIPTION.value,
            public_model_id=resolution.public_model_id,
            error_type=error_type,
            language=language,
            lineage=runtime_lineage(
                resolution, served_artifact=resolution.artifact.id, service_version="unknown"
            ),
        )
