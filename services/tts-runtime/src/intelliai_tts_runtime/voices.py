"""Voice resolution — public identity in, engine reference out.

The runtime's half of the voice ownership split (M3 design review §5):
the gateway/product side owns what voices EXIST and what they're called;
this module owns how a public voice id becomes something an engine can
render. Engine references never cross this boundary outward; public ids
never cross it inward past this point.

The skeleton's voices are deliberately NON-product placeholder names
("reference-*"): launch voice naming is a founder decision that binds
with the first real engine, and nothing here may pre-empt it. When the
Kokoro engine arrives, this map becomes deployment configuration keyed
by the same resolve() seam.
"""

from typing import Final

from intelliai_runtime_contract import RuntimeErrorType
from intelliai_runtime_core import RuntimeServiceError

DEFAULT_VOICE: Final = "reference-alto"

# public voice id -> engine voice reference. The reference engine renders
# "tone:<base-hz>" references; real engines get their own reference forms.
_VOICES: Final[dict[str, str]] = {
    "reference-alto": "tone:440",
    "reference-bass": "tone:220",
}


def resolve(voice: str | None) -> tuple[str, str]:
    """None -> the default voice, made visible: returns (public_id, engine_ref)."""
    public_id = voice if voice is not None else DEFAULT_VOICE
    engine_ref = _VOICES.get(public_id)
    if engine_ref is None:
        raise RuntimeServiceError(
            RuntimeErrorType.INVALID_INPUT,
            f"voice {public_id!r} is not served by this runtime",
            param="voice",
        )
    return public_id, engine_ref


def voice_ids() -> tuple[str, ...]:
    """Public identifiers this runtime serves (operational introspection)."""
    return tuple(_VOICES)
