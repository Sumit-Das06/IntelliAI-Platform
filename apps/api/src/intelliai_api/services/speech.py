"""SpeechService — the gateway's half of the synthesis flow.

Owns exactly what ADR-0016 assigns the gateway: registry resolution
(model AND public voice — voices are product vocabulary, validated on the
product plane before a request ever crosses to a runtime), runtime
invocation through the client seam, TOTAL translation of runtime failures
into the public error contract (ADR-0009), and the platform accounting
event. Customers never learn which runtime, engine, foundation model, or
engine voice token served them — the public surface speaks public model
names, public voice names, and the public taxonomy, nothing else.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

import structlog

from intelliai_api.core.errors import InternalError, InvalidRequestError, ServiceUnavailableError
from intelliai_api.entitlements import EntitlementService
from intelliai_api.limits import CapabilityAdmission
from intelliai_api.metering import UsageRecorder, runtime_lineage
from intelliai_api.registry import Registry, Resolution
from intelliai_api.runtimes import RuntimeCallError, RuntimeClient, RuntimeUnavailableError
from intelliai_api.services.auth import AuthContext
from intelliai_api.services.runtime_errors import translate_runtime_error
from intelliai_runtime_contract import (
    Capability,
    RuntimeErrorType,
    SpeechSynthesisRequest,
    UsageUnit,
)

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SpeechOutcome:
    """What the route renders: the audio plus its accounting facts."""

    audio: bytes
    media_type: str
    public_model_id: str
    voice: str  # the PUBLIC voice that served (default resolution visible)
    characters: float
    audio_seconds: float


class SpeechService:
    def __init__(
        self,
        registry: Registry,
        clients: Mapping[str, RuntimeClient],
        usage: UsageRecorder | None = None,
        admission: CapabilityAdmission | None = None,
        entitlements: EntitlementService | None = None,
    ) -> None:
        self._registry = registry
        self._clients = clients
        self._usage = usage
        self._admission = admission
        self._entitlements = entitlements

    async def synthesize(
        self,
        *,
        auth: AuthContext,
        public_model_id: str,
        text: str,
        voice: str | None,
        speed: float | None,
        language: str | None = None,
        idempotency_key: str | None = None,
    ) -> SpeechOutcome:
        resolution = self._registry.resolve(public_model_id)  # unknown -> 404 model_not_found
        if resolution.capability is not Capability.SPEECH_SYNTHESIS:
            raise InvalidRequestError(
                f"The model {public_model_id!r} does not support speech synthesis.",
                param="model",
                code="capability_mismatch",
            )
        # Voice validation is PRODUCT-plane business: the catalog says what
        # exists; the runtime only ever renders catalog-blessed identities.
        if voice is not None:
            known = {record.id for record in self._registry.list_voices(public_model_id)}
            if voice not in known:
                raise InvalidRequestError(
                    f"The voice {voice!r} does not exist for this model. "
                    "List available voices at GET /v1/audio/voices.",
                    param="voice",
                    code="voice_not_found",
                )
        # Capability-scoped admission: only knowable HERE, after the
        # registry says what this request actually is. Capacity is
        # capability-specific (M3 measured TTS plateauing at 0.64 rps),
        # so a shared request-per-second budget across capabilities would
        # be meaningless — a request is not a unit of cost.
        if self._admission is not None:
            await self._admission.check_capability(
                organization_id=auth.organization_public_id,
                plan_id=auth.organization.plan,
                capability=Capability.SPEECH_SYNTHESIS.value,
            )
        # Entitlement AFTER protection: a caller who is over their plan
        # allowance is also usually going too fast, and the cheaper
        # Redis check should reject them before we aggregate the ledger.
        if self._entitlements is not None:
            await self._entitlements.check(
                organization_id=auth.organization_id,
                organization_public_id=auth.organization_public_id,
                plan_id=auth.organization.plan,
                spend_limit=auth.organization.spend_limit,
            )

        client = self._clients.get(resolution.service)
        if client is None:
            logger.error("runtime_client_missing", service=resolution.service)
            raise InternalError("The service is misconfigured.")

        try:
            audio, envelope = await client.synthesize(
                SpeechSynthesisRequest(
                    text=text, voice=voice, speed=speed, model=resolution.artifact.id
                )
            )
        except RuntimeCallError as exc:
            await self._record_failure(auth, resolution, language, exc.error.type)
            raise translate_runtime_error(
                exc.error.type, exc.error.message, exc.error.param
            ) from exc
        except RuntimeUnavailableError as exc:
            await self._record_failure(auth, resolution, language, None)
            raise ServiceUnavailableError(
                "Speech synthesis is temporarily unavailable. Retry shortly.",
                code="runtime_unavailable",
                retry_after=1,
            ) from exc

        characters = sum(
            usage.amount for usage in envelope.usage if usage.unit is UsageUnit.CHARACTERS
        )
        # The permanent commercial fact (ADR-0021), written before the
        # response is serialized, inside this request's own transaction.
        if self._usage is not None:
            await self._usage.record_success(
                auth=auth,
                capability=Capability.SPEECH_SYNTHESIS.value,
                public_model_id=public_model_id,
                quantities={
                    UsageUnit.CHARACTERS.value: Decimal(str(characters)),
                    # Measured, not billed today — the input to
                    # cost-to-serve margin. Meter everything measured.
                    UsageUnit.AUDIO_SECONDS.value: Decimal(
                        str(round(envelope.output.duration_seconds, 6))
                    ),
                },
                language=language,
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
            "speech.completed",
            organization_id=auth.organization_public_id,
            model=public_model_id,
            voice=envelope.output.voice,
            characters=characters,
            audio_seconds=round(envelope.output.duration_seconds, 3),
        )
        return SpeechOutcome(
            audio=audio,
            media_type="audio/wav",
            public_model_id=public_model_id,
            voice=envelope.output.voice,
            characters=characters,
            audio_seconds=envelope.output.duration_seconds,
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
            capability=Capability.SPEECH_SYNTHESIS.value,
            public_model_id=resolution.public_model_id,
            error_type=error_type,
            language=language,
            lineage=runtime_lineage(
                resolution, served_artifact=resolution.artifact.id, service_version="unknown"
            ),
        )
