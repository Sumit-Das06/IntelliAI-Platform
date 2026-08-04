"""Reading registry state: which artifact serves which promise.

Evaluation must measure *the artifact the registry selected*, never one an
operator named — a benchmark built on a claim records the claim, not the
system. But evaluation lives outside the gateway and depends only on the
runtime contract, so it reads the registry's exported **resolution
manifest** rather than importing the registry.

**This module deliberately implements no routing.** Every entry in the
manifest is already resolved; a lookup is exact, and a miss is a refusal
naming what the manifest holds. A reader that fell back from `hi` to the
default route would be making a routing decision — quietly, in the
evaluation plane, about a language the registry may have deliberately
refused. The registry decides; this reads the decision.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

SUPPORTED_SCHEMA_VERSION = 1


class UnservedError(LookupError):
    """The registry does not serve this — so there is nothing to evaluate."""


class ResolvedServing(BaseModel):
    """One resolved route: the registry's answer, as a record."""

    model_config = ConfigDict(frozen=True)

    language: str | None  # None = the default route
    status: str | None  # None = the default route carries no ladder rung
    artifact: str | None = None
    artifact_version: int | None = None
    deployment: str | None = None

    @property
    def is_served(self) -> bool:
        return self.artifact is not None


class ResolvedVoice(BaseModel):
    """One voice and the artifact that renders it."""

    model_config = ConfigDict(frozen=True)

    voice: str
    languages: list[str]
    artifact: str
    artifact_version: int
    deployment: str


class ManifestModel(BaseModel):
    """One public model's resolved routes and voices."""

    model_config = ConfigDict(frozen=True)

    public_model: str
    capability: str
    service: str
    routes: list[ResolvedServing]
    voices: list[ResolvedVoice] = Field(default_factory=list)


class ResolutionManifest(BaseModel):
    """Registry state as the evaluation plane sees it."""

    model_config = ConfigDict(frozen=True)

    schema_version: int
    models: list[ManifestModel]

    def model_entry(self, public_model: str) -> ManifestModel:
        for entry in self.models:
            if entry.public_model == public_model:
                return entry
        known = ", ".join(entry.public_model for entry in self.models)
        msg = f"the manifest has no public model {public_model!r}; it has: {known}"
        raise UnservedError(msg)

    def resolve(self, public_model: str, language: str | None) -> ResolvedServing:
        """The registry's answer for this slice — exact lookup, no fallback.

        Raises :class:`UnservedError` when the manifest has no entry (the
        registry never decided) or when the entry is a refusal (it decided
        *not* to serve). Both are reasons there is no measurement to take,
        and neither is a reason to substitute another artifact.
        """
        entry = self.model_entry(public_model)
        for route in entry.routes:
            if route.language == language:
                if not route.is_served:
                    msg = (
                        f"{public_model!r} does not serve {language!r} "
                        f"(status: {route.status}); there is nothing to evaluate"
                    )
                    raise UnservedError(msg)
                return route
        declared = ", ".join(
            "<default>" if route.language is None else route.language for route in entry.routes
        )
        msg = (
            f"{public_model!r} has no route for {language!r}; the manifest resolves: {declared}. "
            "Evaluation does not fall back — that would be routing."
        )
        raise UnservedError(msg)

    def resolve_voice(self, public_model: str, voice: str) -> ResolvedVoice:
        entry = self.model_entry(public_model)
        for record in entry.voices:
            if record.voice == voice:
                return record
        known = ", ".join(record.voice for record in entry.voices) or "none"
        msg = f"{public_model!r} has no voice {voice!r}; the manifest resolves: {known}"
        raise UnservedError(msg)


def load_manifest(path: Path) -> ResolutionManifest:
    """Load registry state, refusing a schema this reader does not know."""
    manifest = ResolutionManifest.model_validate(json.loads(path.read_text(encoding="utf-8")))
    if manifest.schema_version != SUPPORTED_SCHEMA_VERSION:
        msg = (
            f"resolution manifest schema {manifest.schema_version} is not "
            f"{SUPPORTED_SCHEMA_VERSION}; refusing rather than guessing at fields"
        )
        raise UnservedError(msg)
    return manifest
