"""Voice resolution: public identity in, engine reference out."""

import pytest

from intelliai_runtime_contract import RuntimeErrorType
from intelliai_runtime_core import RuntimeServiceError
from intelliai_tts_runtime.voices import (
    DEFAULT_VOICE,
    KOKORO_VOICES,
    REFERENCE_VOICES,
    for_engine,
)


def test_none_resolves_to_the_default_voice_visibly() -> None:
    public_id, engine_ref = REFERENCE_VOICES.resolve(None)
    assert public_id == DEFAULT_VOICE  # default resolution is made visible
    assert engine_ref.startswith("tone:")


def test_known_voice_resolves_to_its_engine_reference() -> None:
    public_id, engine_ref = REFERENCE_VOICES.resolve("reference-bass")
    assert public_id == "reference-bass"
    assert engine_ref == "tone:220"


def test_unknown_voice_is_invalid_input_with_param() -> None:
    with pytest.raises(RuntimeServiceError) as exc_info:
        REFERENCE_VOICES.resolve("af_heart")  # engine tokens are NOT public identities
    assert exc_info.value.error_type is RuntimeErrorType.INVALID_INPUT
    assert exc_info.value.param == "voice"


def test_every_engine_serves_the_same_public_identities() -> None:
    # The voice-rebinding law, live: switching the engine rebinds voices,
    # never renames them. The public API surface is engine-independent.
    assert REFERENCE_VOICES.voice_ids() == KOKORO_VOICES.voice_ids()
    assert REFERENCE_VOICES.default_voice == KOKORO_VOICES.default_voice
    assert for_engine("reference") is REFERENCE_VOICES
    assert for_engine("kokoro") is KOKORO_VOICES


def test_served_identities_are_placeholders_never_engine_tokens() -> None:
    # Launch voice naming is a founder decision (pending a listening
    # session); the placeholders must not pre-empt it, and no engine
    # token shape may leak into public ids.
    for voice_map in (REFERENCE_VOICES, KOKORO_VOICES):
        for public_id in voice_map.voice_ids():
            assert public_id.startswith("reference-")
            assert not public_id.startswith(("af_", "am_", "bf_", "bm_", "tone:"))


def test_kokoro_bindings_target_engine_voice_references() -> None:
    # Bindings are the runtime's private mechanics: engine tokens on the
    # right-hand side only, resolved from public ids, never exposed.
    assert KOKORO_VOICES.resolve("reference-alto") == ("reference-alto", "af_heart")
    assert KOKORO_VOICES.resolve("reference-bass") == ("reference-bass", "am_michael")
