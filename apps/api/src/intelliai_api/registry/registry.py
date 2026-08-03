"""The Registry: composed from records, validated eagerly, queried by id.

Every integrity rule runs at composition time — a catalog that is
inconsistent or tries to route to a non-commercial artifact raises
``ValueError`` immediately, so a misconfigured gateway fails at startup,
never at request time (the same fail-fast posture as Settings).
"""

from collections.abc import Iterable

from intelliai_api.core.errors import ResourceNotFoundError
from intelliai_api.registry.records import (
    ArtifactRecord,
    PublicModelRecord,
    PublicVoiceRecord,
    Resolution,
)


class ModelNotFoundError(ResourceNotFoundError):
    """Public model identifier the platform does not serve."""

    def __init__(self, model_id: str) -> None:
        super().__init__(
            f"The model {model_id!r} does not exist or you do not have access to it.",
            code="model_not_found",
            param="model",
        )


class Registry:
    """Immutable resolution authority over a validated catalog."""

    def __init__(
        self,
        *,
        artifacts: Iterable[ArtifactRecord],
        models: Iterable[PublicModelRecord],
        voices: Iterable[PublicVoiceRecord] = (),
    ) -> None:
        self._artifacts: dict[str, ArtifactRecord] = {}
        for artifact in artifacts:
            if artifact.id in self._artifacts:
                msg = f"duplicate artifact id {artifact.id!r}"
                raise ValueError(msg)
            self._artifacts[artifact.id] = artifact

        self._models: dict[str, PublicModelRecord] = {}
        for model in models:
            if model.id in self._models:
                msg = f"duplicate public model id {model.id!r}"
                raise ValueError(msg)
            routed = self._artifacts.get(model.artifact_id)
            if routed is None:
                msg = f"public model {model.id!r} routes to unknown artifact {model.artifact_id!r}"
                raise ValueError(msg)
            if routed.capability is not model.capability:
                msg = (
                    f"public model {model.id!r} ({model.capability}) routes to artifact "
                    f"{routed.id!r} of different capability ({routed.capability})"
                )
                raise ValueError(msg)
            # The license gate (ADR-0005/ADR-0017): recording a
            # non-commercial artifact is legal; ROUTING to one is not.
            if not routed.license.commercial_use:
                msg = (
                    f"public model {model.id!r} routes to artifact {routed.id!r} "
                    f"without a commercial-use license verdict "
                    f"(license={routed.license.license!r}, "
                    f"verified {routed.license.verified_on.isoformat()})"
                )
                raise ValueError(msg)
            self._models[model.id] = model

        self._voices: dict[str, PublicVoiceRecord] = {}
        for voice in voices:
            if voice.id in self._voices:
                msg = f"duplicate public voice id {voice.id!r}"
                raise ValueError(msg)
            if voice.model not in self._models:
                msg = f"public voice {voice.id!r} belongs to unknown model {voice.model!r}"
                raise ValueError(msg)
            self._voices[voice.id] = voice

    def resolve(self, public_model_id: str) -> Resolution:
        """Answer routing's one question; raise ModelNotFoundError otherwise."""
        model = self._models.get(public_model_id)
        if model is None:
            raise ModelNotFoundError(public_model_id)
        return Resolution(
            public_model_id=model.id,
            capability=model.capability,
            service=model.service,
            artifact=self._artifacts[model.artifact_id],
        )

    def list_models(self) -> tuple[PublicModelRecord, ...]:
        """Every public model, catalog order — the `/v1/models` source."""
        return tuple(self._models.values())

    def public_model(self, public_model_id: str) -> PublicModelRecord:
        """The catalog record itself (product facts, no routing)."""
        model = self._models.get(public_model_id)
        if model is None:
            raise ModelNotFoundError(public_model_id)
        return model

    def list_voices(self, public_model_id: str | None = None) -> tuple[PublicVoiceRecord, ...]:
        """Public voices, catalog order — the `/v1/audio/voices` source."""
        return tuple(
            voice
            for voice in self._voices.values()
            if public_model_id is None or voice.model == public_model_id
        )
