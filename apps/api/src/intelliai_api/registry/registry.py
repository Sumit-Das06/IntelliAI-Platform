"""The Registry: composed from records, validated eagerly, queried by id.

Every integrity rule runs at composition time — a catalog that is
inconsistent or tries to route to a non-commercial artifact raises
``ValueError`` immediately, so a misconfigured gateway fails at startup,
never at request time (the same fail-fast posture as Settings).
"""

from collections.abc import Iterable

from intelliai_api.core.errors import InvalidRequestError, ResourceNotFoundError
from intelliai_api.registry.records import (
    ArtifactRecord,
    LanguageStatus,
    PublicModelRecord,
    PublicVoiceRecord,
    Resolution,
    ServingRoute,
    normalize_language,
)


class ModelNotFoundError(ResourceNotFoundError):
    """Public model identifier the platform does not serve."""

    def __init__(self, model_id: str) -> None:
        super().__init__(
            f"The model {model_id!r} does not exist or you do not have access to it.",
            code="model_not_found",
            param="model",
        )


class LanguageNotSupportedError(InvalidRequestError):
    """A language the platform refuses to serve for this model.

    An honest refusal that names what *is* served — never a silent
    best-effort attempt at a language nobody measured. The refusal is
    itself demand evidence: the request that provoked it is recorded, so
    the Language Policy can be steered by what customers actually ask
    for (M5 design review §11).
    """

    def __init__(self, model_id: str, language: str, *, served: tuple[str, ...]) -> None:
        offer = ", ".join(served) if served else "no additional languages"
        super().__init__(
            f"The model {model_id!r} does not serve the language {language!r}. "
            f"Languages served: {offer}.",
            code="language_not_supported",
            param="language",
        )
        self.model_id = model_id
        self.language = language
        self.served = served


class Registry:
    """Immutable resolution authority over a validated catalog."""

    def __init__(
        self,
        *,
        artifacts: Iterable[ArtifactRecord],
        models: Iterable[PublicModelRecord],
        voices: Iterable[PublicVoiceRecord] = (),
        routes: Iterable[ServingRoute] = (),
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

        # Serving routes: the second resolution input (ADR-0025). Built
        # after models so a route's public model is already known, and
        # before voices so voice bindings can be checked by resolving.
        self._routes: dict[str, list[ServingRoute]] = {}
        for route in routes:
            routed_model = self._models.get(route.public_model_id)
            if routed_model is None:
                msg = f"serving route for unknown public model {route.public_model_id!r}"
                raise ValueError(msg)
            siblings = self._routes.setdefault(route.public_model_id, [])
            for other in siblings:
                # The Specificity Law's tie clause: two equally specific
                # selectors that some single request could both match are
                # a composition error, never a runtime coin-flip. Until
                # Serving Strategies exist (ADR-0025 decision 5), that
                # also means exactly one binding per selector.
                if other.selector.specificity == route.selector.specificity and (
                    other.selector.can_both_match(route.selector)
                ):
                    msg = (
                        f"public model {route.public_model_id!r} has two equally specific "
                        f"routes that can match the same request ({other.selector!r} and "
                        f"{route.selector!r}); one binding per selector until Serving "
                        f"Strategies exist"
                    )
                    raise ValueError(msg)
            artifact_id = route.artifact_id
            if artifact_id is not None:
                routed = self._artifacts.get(artifact_id)
                if routed is None:
                    msg = (
                        f"serving route {route.public_model_id!r}/{route.selector.language!r} "
                        f"routes to unknown artifact {artifact_id!r}"
                    )
                    raise ValueError(msg)
                if routed.capability is not routed_model.capability:
                    msg = (
                        f"serving route {route.public_model_id!r}/{route.selector.language!r} "
                        f"({routed_model.capability}) routes to artifact {routed.id!r} of "
                        f"different capability ({routed.capability})"
                    )
                    raise ValueError(msg)
                if not routed.license.commercial_use:
                    msg = (
                        f"serving route {route.public_model_id!r}/{route.selector.language!r} "
                        f"routes to artifact {routed.id!r} without a commercial-use license "
                        f"verdict (license={routed.license.license!r})"
                    )
                    raise ValueError(msg)
                # The Hindi-GPL lesson: the weights were never the gate.
                path = route.license
                if path is not None and not path.commercial_use:
                    msg = (
                        f"serving route {route.public_model_id!r}/{route.selector.language!r} "
                        f"has a non-commercial serving path (license={path.license!r}); the "
                        f"verdict must cover the whole language-specific path"
                    )
                    raise ValueError(msg)
            siblings.append(route)

        self._voices: dict[str, PublicVoiceRecord] = {}
        for voice in voices:
            if voice.id in self._voices:
                msg = f"duplicate public voice id {voice.id!r}"
                raise ValueError(msg)
            if voice.model not in self._models:
                msg = f"public voice {voice.id!r} belongs to unknown model {voice.model!r}"
                raise ValueError(msg)
            self._validate_voice_binding(voice)
            self._voices[voice.id] = voice

    def _validate_voice_binding(self, voice: PublicVoiceRecord) -> None:
        """A voice's artifact and its languages' routes must agree.

        A voice's sound *is* an artifact-specific asset, so publishing a
        voice for a language the model refuses — or binding it to an
        artifact that language does not route to — is a contradiction the
        build must not ship.
        """
        model = self._models[voice.model]
        bound = voice.artifact_id
        if bound is not None:
            artifact = self._artifacts.get(bound)
            if artifact is None:
                msg = f"public voice {voice.id!r} binds unknown artifact {bound!r}"
                raise ValueError(msg)
            if artifact.capability is not model.capability:
                msg = (
                    f"public voice {voice.id!r} binds artifact {bound!r} of different "
                    f"capability ({artifact.capability} vs {model.capability})"
                )
                raise ValueError(msg)
            if not artifact.license.commercial_use:
                msg = (
                    f"public voice {voice.id!r} binds artifact {bound!r} without a "
                    f"commercial-use license verdict"
                )
                raise ValueError(msg)
        for language in voice.languages:
            try:
                resolved = self.resolve(voice.model, language=language)
            except LanguageNotSupportedError as exc:
                msg = (
                    f"public voice {voice.id!r} claims language {language!r}, which "
                    f"{voice.model!r} does not serve"
                )
                raise ValueError(msg) from exc
            if bound is not None and resolved.artifact.id != bound:
                msg = (
                    f"public voice {voice.id!r} binds artifact {bound!r} but language "
                    f"{language!r} routes to {resolved.artifact.id!r}; a voice's artifact "
                    f"must serve every language the voice claims"
                )
                raise ValueError(msg)

    def _route_for(self, public_model_id: str, language: str | None) -> ServingRoute | None:
        """The most specific matching route, or ``None`` for the default.

        Ties are impossible: composition refuses two equally specific
        selectors that could both match (the Specificity Law).
        """
        matches = [
            route
            for route in self._routes.get(public_model_id, ())
            if route.selector.matches(language=language)
        ]
        if not matches:
            return None
        return max(matches, key=lambda route: route.selector.specificity)

    def resolve(self, public_model_id: str, *, language: str | None = None) -> Resolution:
        """Answer routing's one question; raise ModelNotFoundError otherwise.

        Routing is resolution: the registry is the only component that
        maps a customer's request to an artifact. ``language`` is the
        customer's *declared* intent, normalized to its base subtag —
        detected language is a recorded fact, never a routing input. With
        no declaration (or no matching route) the model's own
        ``artifact_id`` is the default route, which is why today's
        catalog behaves exactly as it did before routes existed.
        """
        model = self._models.get(public_model_id)
        if model is None:
            raise ModelNotFoundError(public_model_id)
        declared = normalize_language(language)
        route = self._route_for(model.id, declared)
        if route is None:
            return Resolution(
                public_model_id=model.id,
                capability=model.capability,
                service=model.service,
                artifact=self._artifacts[model.artifact_id],
            )
        if route.status is LanguageStatus.UNAVAILABLE or route.artifact_id is None:
            raise LanguageNotSupportedError(
                model.id,
                declared or "",
                served=self.served_languages(model.id),
            )
        return Resolution(
            public_model_id=model.id,
            capability=model.capability,
            service=model.service,
            artifact=self._artifacts[route.artifact_id],
            deployment=route.deployment or model.service,
        )

    def language_status(self, public_model_id: str, language: str) -> LanguageStatus | None:
        """This model's ladder rung for a language, or ``None`` if the
        language has no route and therefore no promise — undeclared
        traffic rides the default route, about which we promise nothing."""
        if public_model_id not in self._models:
            raise ModelNotFoundError(public_model_id)
        route = self._route_for(public_model_id, normalize_language(language))
        return route.status if route is not None else None

    def list_languages(self, public_model_id: str) -> tuple[ServingRoute, ...]:
        """Every language route for a model, catalog order — the ladder's
        source of truth for public documentation.

        Returns the *records*, which carry temporary vocabulary
        (artifact ids, deployments). Only the (language, status) pair is
        publishable; any endpoint built on this must project, never
        forward — the leak-guard law, which is why this returns routes
        rather than a ready-made response shape.
        """
        if public_model_id not in self._models:
            raise ModelNotFoundError(public_model_id)
        return tuple(self._routes.get(public_model_id, ()))

    def served_languages(self, public_model_id: str) -> tuple[str, ...]:
        """The languages this model actually serves — every rung above
        ``unavailable``, in catalog order."""
        return tuple(
            route.selector.language
            for route in self._routes.get(public_model_id, ())
            if route.status is not LanguageStatus.UNAVAILABLE
            and route.selector.language is not None
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
