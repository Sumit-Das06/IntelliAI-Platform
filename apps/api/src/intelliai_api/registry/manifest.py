"""The resolution manifest: registry state, exported for readers outside
the gateway.

The evaluation plane must evaluate *the artifact the registry selected*,
not one an operator named — otherwise a benchmark records a claim rather
than a fact, and the one-way chain (serving → evidence → promotion →
registry state → routing) is broken at its first link. But evaluation
cannot import the registry: it lives outside this app and depends only on
the runtime contract (ADR-0001's one-way dependency direction).

The manifest is that seam. It is a **projection**, never a second source
of truth: every entry is the answer `resolve()` gives, computed here and
serialized. The committed copy is checked against a freshly generated one
in CI, so it cannot drift; a reader that has the manifest, a dataset
version, and an artifact version has everything needed to reproduce a
measurement years later, with no operator knowledge in the loop.

Deliberately **pre-resolved**: one entry per route plus one for the
default. A reader looks up an exact key and refuses on a miss — it never
re-implements the Specificity Law, because a reader that falls back is a
reader that routes.
"""

from typing import Any

from intelliai_api.registry.records import LanguageStatus
from intelliai_api.registry.registry import Registry

#: Bumped only when the document's shape changes incompatibly; readers
#: refuse a version they do not know rather than guessing at fields.
MANIFEST_SCHEMA_VERSION = 1


def _serving(registry: Registry, public_model_id: str, language: str | None) -> dict[str, Any]:
    resolution = registry.resolve(public_model_id, language=language)
    return {
        "artifact": resolution.artifact.id,
        "artifact_version": resolution.artifact.version,
        "deployment": resolution.deployment,
    }


def serving_manifest(registry: Registry) -> dict[str, Any]:
    """Every (public model, selector) the registry can resolve, resolved."""
    models: list[dict[str, Any]] = []
    for model in registry.list_models():
        routes: list[dict[str, Any]] = [
            # The default route: what serves a request that declares no
            # language. `language: null` is its key, not a wildcard.
            {"language": None, "status": None, **_serving(registry, model.id, None)}
        ]
        for route in registry.list_languages(model.id):
            entry: dict[str, Any] = {
                "language": route.selector.language,
                "status": route.status.value,
            }
            if route.status is not LanguageStatus.UNAVAILABLE:
                entry.update(_serving(registry, model.id, route.selector.language))
            routes.append(entry)

        voices: list[dict[str, Any]] = []
        for voice in registry.list_voices(model.id):
            resolution = registry.resolve_voice(model.id, voice.id)
            voices.append(
                {
                    "voice": voice.id,
                    "languages": list(voice.languages),
                    "artifact": resolution.artifact.id,
                    "artifact_version": resolution.artifact.version,
                    "deployment": resolution.deployment,
                }
            )

        models.append(
            {
                "public_model": model.id,
                "capability": model.capability.value,
                "service": model.service,
                "routes": routes,
                "voices": voices,
            }
        )
    return {"schema_version": MANIFEST_SCHEMA_VERSION, "models": models}
