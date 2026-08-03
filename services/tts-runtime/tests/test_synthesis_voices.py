"""Voice resolution: public identity in, engine reference out."""

import pytest

from intelliai_runtime_contract import RuntimeErrorType
from intelliai_runtime_core import RuntimeServiceError
from intelliai_tts_runtime.voices import DEFAULT_VOICE, resolve, voice_ids


def test_none_resolves_to_the_default_voice_visibly() -> None:
    public_id, engine_ref = resolve(None)
    assert public_id == DEFAULT_VOICE  # default resolution is made visible
    assert engine_ref.startswith("tone:")


def test_known_voice_resolves_to_its_engine_reference() -> None:
    public_id, engine_ref = resolve("reference-bass")
    assert public_id == "reference-bass"
    assert engine_ref == "tone:220"


def test_unknown_voice_is_invalid_input_with_param() -> None:
    with pytest.raises(RuntimeServiceError) as exc_info:
        resolve("af_heart")  # engine tokens are NOT public identities
    assert exc_info.value.error_type is RuntimeErrorType.INVALID_INPUT
    assert exc_info.value.param == "voice"


def test_served_identities_are_placeholders_never_product_names() -> None:
    # Launch voice naming is a founder decision (M3 step 0, pending); the
    # skeleton must not pre-empt it. Every skeleton voice is explicitly
    # reference-branded, and none leaks an engine token shape.
    for public_id in voice_ids():
        assert public_id.startswith("reference-")
        assert not public_id.startswith(("af_", "am_", "bf_", "bm_"))
