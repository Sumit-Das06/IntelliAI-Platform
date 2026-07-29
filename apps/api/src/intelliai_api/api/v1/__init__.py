"""Version 1 of the public API.

Structure: one package per AI domain, never large single files —

    v1/
        speech/       (M2/M3: transcriptions, speech, voices)
        chat/         (Phase 3)
        vision/       (Phase 3)
        ...

Each domain package exposes an ``APIRouter`` that this package aggregates and
``main.create_app`` mounts under ``/v1``.

Versioning contract: ``v1`` is append-only once stable. Breaking changes go
into a sibling ``v2`` package that coexists with ``v1`` behind its own prefix;
nothing outside the ``api`` layer is version-aware.
"""
