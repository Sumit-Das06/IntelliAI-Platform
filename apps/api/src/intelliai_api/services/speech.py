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

import asyncio
import contextlib
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from decimal import Decimal

import structlog

from intelliai_api.core.errors import InternalError, InvalidRequestError, ServiceUnavailableError
from intelliai_api.entitlements import EntitlementService
from intelliai_api.limits import CapabilityAdmission
from intelliai_api.metering import UsageRecorder, runtime_lineage
from intelliai_api.registry import Registry, Resolution, VoiceNotFoundError
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


#: Bytes of WAV preamble the runtime sends before any audio in streaming
#: mode; subtracted when measuring delivered audio from delivered bytes.
_WAV_HEADER_BYTES = 44
_PCM_BYTES_PER_SECOND = 24_000 * 2  # canonical mono 16-bit 24 kHz


@dataclass(frozen=True)
class SpeechStreamOutcome:
    """What the route streams: accounted bytes plus identity facts.

    ``stream`` is the accounting-wrapped byte iterator — billing happens
    inside it, after delivery ends (complete, failed, or abandoned), per
    the streaming billing law documented on the public route.
    """

    stream: AsyncIterator[bytes]
    media_type: str
    public_model_id: str
    voice: str
    characters: float


def _voice_language(registry: Registry, public_model_id: str, voice: str | None) -> str | None:
    """The language a voice declares, when it declares exactly one.

    The synthesis half of the Ledger Fact Invariant. Transcription records
    the language the engine *observed*; synthesis has nothing to observe,
    so the fact available is the one the catalog states about the voice
    that rendered the audio. A multilingual voice states no single
    language, and with no public language input (F-M5-7) there is nothing
    to fall back on — the honest record is then no record at all.
    """
    if voice is None:
        return None
    try:
        record = registry.voice(public_model_id, voice)
    except VoiceNotFoundError:
        # The runtime named a voice the catalog does not have: a real
        # defect, but never one that fails a request the customer already
        # paid for. Loud in the logs, absent from the ledger.
        logger.warning("voice_not_in_catalog", model=public_model_id, voice=voice)
        return None
    return record.languages[0] if len(record.languages) == 1 else None


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
        idempotency_key: str | None = None,
    ) -> SpeechOutcome:
        # Capability BEFORE routing, so the caller hears about the more
        # fundamental mistake first.
        model = self._registry.public_model(public_model_id)  # unknown -> 404 model_not_found
        if model.capability is not Capability.SPEECH_SYNTHESIS:
            raise InvalidRequestError(
                f"The model {public_model_id!r} does not support speech synthesis.",
                param="model",
                code="capability_mismatch",
            )
        # Routing is resolution, and for synthesis the VOICE is the routing
        # key: a voice's sound is an artifact-specific asset, so the voice
        # determines which artifact renders it (M5 design §4.3). An unknown
        # voice is refused here, by the registry, before any plane is
        # crossed — the catalog says what exists, and the runtime only ever
        # renders catalog-blessed identities.
        resolution = self._registry.resolve_voice(public_model_id, voice)
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

        # Keyed by DEPLOYMENT, not by service: one capability service is a
        # set of deployments (ADR-0026), and resolution says which one
        # hosts the artifact it chose. Today's topology is the degenerate
        # case — one deployment per capability, named for the service.
        client = self._clients.get(resolution.deployment)
        if client is None:
            logger.error(
                "runtime_client_missing",
                deployment=resolution.deployment,
                service=resolution.service,
            )
            raise InternalError("The service is misconfigured.")

        requested_language = _voice_language(self._registry, public_model_id, voice)
        try:
            audio, envelope = await client.synthesize(
                SpeechSynthesisRequest(
                    text=text, voice=voice, speed=speed, model=resolution.artifact.id
                )
            )
        except RuntimeCallError as exc:
            await self._record_failure(auth, resolution, requested_language, exc.error.type)
            raise translate_runtime_error(
                exc.error.type, exc.error.message, exc.error.param
            ) from exc
        except RuntimeUnavailableError as exc:
            await self._record_failure(auth, resolution, requested_language, None)
            raise ServiceUnavailableError(
                "Speech synthesis is temporarily unavailable. Retry shortly.",
                code="runtime_unavailable",
                retry_after=1,
            ) from exc

        characters = sum(
            usage.amount for usage in envelope.usage if usage.unit is UsageUnit.CHARACTERS
        )
        # Closes M4's TTS-language gap. The voice that ACTUALLY rendered is
        # the one the runtime reports back — which also covers the request
        # that named no voice and took the runtime's default.
        served_language = _voice_language(self._registry, public_model_id, envelope.output.voice)
        # The permanent commercial fact (ADR-0021), written before the
        # response is serialized, inside this request's own transaction.
        #
        # M35 billing law: synthesis bills CHARACTERS and nothing else.
        # `quantities` is the rated set — rating prices every unit a
        # billable event carries, and `audio_seconds` has a book price
        # (it is STT's billable unit), so putting the measured duration
        # here would double-charge synthesis. The duration is still
        # metered — as telemetry beside the lineage, never as a rated
        # quantity. Meter everything measured; bill exactly one unit.
        if self._usage is not None:
            await self._usage.record_success(
                auth=auth,
                capability=Capability.SPEECH_SYNTHESIS.value,
                public_model_id=public_model_id,
                quantities={UsageUnit.CHARACTERS.value: Decimal(str(characters))},
                language=served_language,
                lineage={
                    **runtime_lineage(
                        resolution,
                        served_artifact=envelope.model,
                        service_version=envelope.runtime.service_version,
                    ),
                    "measured_audio_seconds": round(envelope.output.duration_seconds, 6),
                },
                idempotency_key=idempotency_key,
            )
        # The request-event side of the daily reconciliation invariant:
        # successful billable responses must equal billable ledger rows.
        logger.info(
            "speech.completed",
            organization_id=auth.organization_public_id,
            model=public_model_id,
            voice=envelope.output.voice,
            language=served_language,
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

    async def synthesize_stream(
        self,
        *,
        auth: AuthContext,
        public_model_id: str,
        text: str,
        voice: str | None,
        speed: float | None,
        idempotency_key: str | None = None,
    ) -> SpeechStreamOutcome:
        """The progressive form (M36): same product laws, audio early.

        Every pre-flight check is IDENTICAL to `synthesize` — capability,
        voice resolution, admission, entitlement — and every pre-stream
        failure raises the same public errors. Once audio begins, the
        billing law is: **delivery started = the request's characters are
        billed** (F1 — successful generation, not socket completion,
        defines billability; a customer who disconnects mid-stream chose
        to abandon delivered work). A runtime failure mid-stream instead
        records the non-billable capacity row, exactly like today's
        accepted-then-failed law.
        """
        model = self._registry.public_model(public_model_id)
        if model.capability is not Capability.SPEECH_SYNTHESIS:
            raise InvalidRequestError(
                f"The model {public_model_id!r} does not support speech synthesis.",
                param="model",
                code="capability_mismatch",
            )
        resolution = self._registry.resolve_voice(public_model_id, voice)
        if self._admission is not None:
            await self._admission.check_capability(
                organization_id=auth.organization_public_id,
                plan_id=auth.organization.plan,
                capability=Capability.SPEECH_SYNTHESIS.value,
            )
        if self._entitlements is not None:
            await self._entitlements.check(
                organization_id=auth.organization_id,
                organization_public_id=auth.organization_public_id,
                plan_id=auth.organization.plan,
                spend_limit=auth.organization.spend_limit,
            )
        client = self._clients.get(resolution.deployment)
        if client is None:
            logger.error(
                "runtime_client_missing",
                deployment=resolution.deployment,
                service=resolution.service,
            )
            raise InternalError("The service is misconfigured.")

        requested_language = _voice_language(self._registry, public_model_id, voice)
        try:
            byte_iter, envelope = await client.synthesize_stream(
                SpeechSynthesisRequest(
                    text=text, voice=voice, speed=speed, model=resolution.artifact.id, stream=True
                )
            )
        except RuntimeCallError as exc:
            await self._record_failure(auth, resolution, requested_language, exc.error.type)
            raise translate_runtime_error(
                exc.error.type, exc.error.message, exc.error.param
            ) from exc
        except RuntimeUnavailableError as exc:
            await self._record_failure(auth, resolution, requested_language, None)
            raise ServiceUnavailableError(
                "Speech synthesis is temporarily unavailable. Retry shortly.",
                code="runtime_unavailable",
                retry_after=1,
            ) from exc

        characters = sum(
            usage.amount for usage in envelope.usage if usage.unit is UsageUnit.CHARACTERS
        )
        served_voice = envelope.output.voice
        served_language = _voice_language(self._registry, public_model_id, served_voice)
        lineage = runtime_lineage(
            resolution,
            served_artifact=envelope.model,
            service_version=envelope.runtime.service_version,
        )

        async def accounted() -> AsyncIterator[bytes]:
            delivered_bytes = 0
            runtime_broke = False
            try:
                async for chunk in byte_iter:
                    delivered_bytes += len(chunk)
                    yield chunk
            except Exception:  # transport failure mid-stream: OUR side broke
                runtime_broke = True
                logger.warning("speech_stream_interrupted", delivered_bytes=delivered_bytes)
            finally:
                audio_seconds = max(0, delivered_bytes - _WAV_HEADER_BYTES) / _PCM_BYTES_PER_SECOND
                # The write is shielded: a client disconnect cancels THIS
                # generator, never the commercial record. A replay is
                # absorbed by the request id (at-most-once law).
                if self._usage is not None:
                    if runtime_broke or delivered_bytes <= _WAV_HEADER_BYTES:
                        record = self._usage.record_runtime_failure(
                            auth=auth,
                            capability=Capability.SPEECH_SYNTHESIS.value,
                            public_model_id=public_model_id,
                            error_type=RuntimeErrorType.INTERNAL if runtime_broke else None,
                            language=served_language,
                            lineage=lineage,
                        )
                    else:
                        record = self._usage.record_streamed_success(
                            auth=auth,
                            capability=Capability.SPEECH_SYNTHESIS.value,
                            public_model_id=public_model_id,
                            quantities={UsageUnit.CHARACTERS.value: Decimal(str(characters))},
                            language=served_language,
                            lineage={
                                **lineage,
                                "measured_audio_seconds": round(audio_seconds, 6),
                                "delivery": "streamed",
                            },
                            idempotency_key=idempotency_key,
                        )
                    with contextlib.suppress(Exception):
                        await asyncio.shield(asyncio.ensure_future(record))
                logger.info(
                    "speech.streamed",
                    organization_id=auth.organization_public_id,
                    model=public_model_id,
                    voice=served_voice,
                    language=served_language,
                    characters=characters,
                    audio_seconds=round(audio_seconds, 3),
                    complete=not runtime_broke,
                )

        return SpeechStreamOutcome(
            stream=accounted(),
            media_type="audio/wav",
            public_model_id=public_model_id,
            voice=served_voice,
            characters=characters,
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
