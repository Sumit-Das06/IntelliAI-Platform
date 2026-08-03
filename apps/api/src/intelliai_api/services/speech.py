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

import structlog

from intelliai_api.core.errors import InternalError, InvalidRequestError, ServiceUnavailableError
from intelliai_api.registry import Registry
from intelliai_api.runtimes import RuntimeCallError, RuntimeClient, RuntimeUnavailableError
from intelliai_api.services.auth import AuthContext
from intelliai_api.services.runtime_errors import translate_runtime_error
from intelliai_runtime_contract import Capability, SpeechSynthesisRequest, UsageUnit

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
    def __init__(self, registry: Registry, clients: Mapping[str, RuntimeClient]) -> None:
        self._registry = registry
        self._clients = clients

    async def synthesize(
        self,
        *,
        auth: AuthContext,
        public_model_id: str,
        text: str,
        voice: str | None,
        speed: float | None,
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
            raise translate_runtime_error(
                exc.error.type, exc.error.message, exc.error.param
            ) from exc
        except RuntimeUnavailableError as exc:
            raise ServiceUnavailableError(
                "Speech synthesis is temporarily unavailable. Retry shortly.",
                code="runtime_unavailable",
                retry_after=1,
            ) from exc

        characters = sum(
            usage.amount for usage in envelope.usage if usage.unit is UsageUnit.CHARACTERS
        )
        # The platform accounting event: billing, usage dashboards, and
        # analytics consume THIS, emitted only by the gateway, in public
        # vocabulary (public model id, public voice id, org id).
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
