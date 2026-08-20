"""Speech synthesis capability schemas — the smallest surface that serves M3.

The result is metadata-only BY DESIGN: synthesized audio travels as the
transport body (ADR-0020), so the contract stays transport-free precisely
by not modeling it — the mirror image of transcription, where the input
audio travels by transport. Voice identifiers here are PUBLIC product
names; engine voice tokens, embeddings, and other voice-engine internals
must never appear in this contract (M3 design review §5). Fields are
added when a real consumer needs them (additive-with-defaults, ADR-0016),
never speculatively.
"""

from pydantic import Field

from intelliai_runtime_contract.base import ContractModel
from intelliai_runtime_contract.envelopes import RuntimeResponse


class SpeechSynthesisRequest(ContractModel):
    """Capability params. The synthesized audio travels back by transport,
    not here — this is what the runtime needs to know, nothing more."""

    text: str = Field(min_length=1)  # what to say; the one required input
    # PUBLIC voice identifier (product vocabulary, never an engine voice
    # token). None = the runtime's default voice; the runtime maps the id
    # to its engine reference and answers `invalid_input` for unknowns.
    voice: str | None = None
    language: str | None = None  # BCP-47-ish hint for multilingual voices
    # Pace multiplier: 1.0 = the voice's natural rate. Typed now with
    # pinned semantics; runtimes that cannot honor a value answer
    # `invalid_input` rather than silently ignoring it.
    speed: float | None = Field(default=None, gt=0)
    #: M36 (additive): ask the runtime to deliver audio progressively —
    #: the response body starts with the first synthesized chunk instead
    #: of the merged whole. False preserves the exact v1 behavior.
    stream: bool = False
    # The artifact identifier the gateway's registry resolved (never a
    # public model name, never an engine name). None = the default slot —
    # the same slot pattern as transcription.
    model: str | None = None


class SpeechSynthesisResult(ContractModel):
    """What the runtime produced — the facts ABOUT the audio, never the
    audio. `voice` is the public identifier that actually served (default
    resolution made visible); `characters` is what usage accounting bills."""

    duration_seconds: float = Field(ge=0)
    sample_rate_hz: int = Field(gt=0)
    voice: str = Field(min_length=1)
    characters: int = Field(ge=0)


SpeechSynthesisResponse = RuntimeResponse[SpeechSynthesisResult]
