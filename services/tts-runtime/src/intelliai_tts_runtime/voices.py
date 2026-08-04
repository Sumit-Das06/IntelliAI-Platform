"""Voice resolution — public identity in, engine reference out.

The runtime's half of the voice ownership split (M3 design review §5):
the gateway/product side owns what voices EXIST and what they're called;
this module owns how a public voice id becomes something an engine can
render. Engine references never cross this boundary outward; public ids
never cross it inward past this point.

Public ids are deliberately NON-product placeholders (founder decision
2026-08-03: placeholders until the launch voices have been listened to —
engineering does not wait on branding). The voice-rebinding law, live:
**every engine serves the SAME public ids** — switching the engine
rebinds voices, never renames them, so the API surface is identical
whether the reference engine or Kokoro is deployed.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from intelliai_runtime_contract import RuntimeErrorType
from intelliai_runtime_core import RuntimeServiceError

DEFAULT_VOICE: Final = "reference-alto"


@dataclass(frozen=True)
class VoiceMap:
    """One engine's bindings: public voice id -> engine voice reference."""

    default_voice: str
    bindings: Mapping[str, str]

    def resolve(self, voice: str | None) -> tuple[str, str]:
        """None -> the default voice, made visible: (public_id, engine_ref)."""
        public_id = voice if voice is not None else self.default_voice
        engine_ref = self.bindings.get(public_id)
        if engine_ref is None:
            raise RuntimeServiceError(
                RuntimeErrorType.INVALID_INPUT,
                f"voice {public_id!r} is not served by this runtime",
                param="voice",
            )
        return public_id, engine_ref

    def voice_ids(self) -> tuple[str, ...]:
        """Public identifiers this runtime serves (operational introspection)."""
        return tuple(self.bindings)


REFERENCE_VOICES: Final = VoiceMap(
    default_voice=DEFAULT_VOICE,
    bindings={"reference-alto": "tone:440", "reference-bass": "tone:220"},
)

# The same PUBLIC identities, served by Kokoro voice packs (the engine
# references name hash-pinned artifact files, never anything customers see).
KOKORO_VOICES: Final = VoiceMap(
    default_voice=DEFAULT_VOICE,
    bindings={"reference-alto": "af_heart", "reference-bass": "am_michael"},
)

_BY_ENGINE: Final[dict[str, VoiceMap]] = {
    "reference": REFERENCE_VOICES,
    "kokoro": KOKORO_VOICES,
}


def for_engine(engine: str) -> VoiceMap:
    """Deployment wiring: which bindings the configured engine serves."""
    return _BY_ENGINE[engine]


class VoiceCatalog:
    """Which voice bindings each LOADED engine serves — the per-slot map.

    Keyed by the **engine instance**, which is the one thing both callers
    hold: the request path, after slot selection, and the warm-up probe,
    which runtime-core hands nothing else (and runtime-core is not
    changing for this). Keying by engine also makes the ownership law
    unbypassable rather than merely documented: a voice cannot be
    resolved before a slot has been selected, because the selected
    engine IS the key.

    Multi-slot hosting is why this exists. With one engine a global map
    was indistinguishable from a per-slot one; with several, a voice
    belongs to the artifact that can actually render it.
    """

    def __init__(self) -> None:
        self._by_engine: dict[object, VoiceMap] = {}

    def bind(self, engine: object, voice_map: VoiceMap) -> None:
        """Record a loaded engine's bindings — called by the slot loader,
        so binding happens exactly where the engine is constructed."""
        self._by_engine[engine] = voice_map

    def voices_for(self, engine: object) -> VoiceMap:
        """This engine's bindings; a miss is a wiring defect, not input."""
        voice_map = self._by_engine.get(engine)
        if voice_map is None:  # pragma: no cover — unreachable by construction
            msg = "engine was loaded without voice bindings"
            raise RuntimeError(msg)
        return voice_map
