"""The M30 punctuation stage: word-copy law, fail-open law, pinned identity.

What this file holds: the stage may only APPEND supported marks to copied
words (never rewrite, never drop, never reorder); every stage problem
yields the raw transcript on a 200; gating follows the route-resolved
language, never a client's "auto"; and the artifact identity is pinned
byte-for-byte. Real-model behavior runs only where the seeded artifact and
the punctuation extra exist (dev machines) — CI proves the laws through
the pure core and the seams.
"""

import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from helpers import wav_bytes
from intelliai_runtime_contract import (
    RuntimeResponse,
    TranscriptionResult,
    TranscriptionSegment,
)
from intelliai_stt_runtime.config import Settings
from intelliai_stt_runtime.engines.punctuation import (
    CONFIG_FILENAME,
    ONNX_FILENAME,
    POST_LABEL_MAP,
    POST_LABELS,
    PUNCTUATION_ARTIFACT,
    PUNCTUATION_FILES,
    SPM_FILENAME,
    SUPPORTED_MARKS,
    PunctuationRestorer,
    PunctuationStageError,
    StageOutcome,
    apply_marks,
    depunct,
    invariant_holds,
    load_punctuation,
    redistribute_segments,
)
from intelliai_stt_runtime.main import create_app

DANDA = "।"


# ── The pure word-copy core ──────────────────────────────────────────────


class TestApplyMarks:
    def test_words_are_copied_verbatim(self) -> None:
        text = "M16 rifle से pH GMT तक"
        out = apply_marks(text, [[], [], [], [","], [], [], [DANDA]])
        assert out == f"M16 rifle से, pH GMT तक{DANDA}"

    def test_edge_tokens_survive_untouched(self) -> None:
        cases = [
            "रोलैंडो ने अपनी M16 राइफल से फायर किया",
            "इसे केमिकल का pH कहा जाता है",
            "वाहन 1200 GMT पर हटाया गया",
            "साइट intelliai.example.com पर जाएँ",
            "बायोडाटा support@example.com पर भेजिए",
            "कुल 2500 रुपये और 7.5 प्रतिशत ब्याज",
            "मैंने नया laptop खरीदा battery life अच्छी है",
            "पंद्रह लोगों का खर्च <unintelligible> हो गया",
        ]
        for text in cases:
            n = len(text.split())
            marks: list[list[str]] = [[] for _ in range(n + 1)]
            marks[-1] = [DANDA]
            out = apply_marks(text, marks)
            assert invariant_holds(text, out), text
            assert "unk" not in out.casefold().replace("unintelligible", "")
            assert out.rsplit(DANDA, 1)[0].split() == text.split()

    def test_empty_text_yields_no_words(self) -> None:
        assert apply_marks("", [[]]) == ""

    def test_slot_count_mismatch_is_refused(self) -> None:
        with pytest.raises(PunctuationStageError):
            apply_marks("एक दो", [[], [DANDA]])

    def test_a_mark_outside_v1_scope_is_refused(self) -> None:
        for bad in ("!", ".", ";"):
            with pytest.raises(PunctuationStageError):
                apply_marks("एक", [[], [bad]])


class TestInvariant:
    def test_marks_pass_and_word_changes_fail(self) -> None:
        assert invariant_holds("मैं घर जा रहा हूँ", f"मैं घर जा रहा हूँ{DANDA}")
        assert not invariant_holds("आप कहाँ जा रहे हैं", "आप कहाँ जा रहे हो?")
        assert not invariant_holds("मैं अपने घर जा रहा हूँ", "मैं घर जा रहा हूँ")

    def test_depunct_matches_the_m29c_semantics(self) -> None:
        zwj = "‍"
        assert depunct(f"क{zwj}ख, ठीक{DANDA}") == "कख ठीक"


class TestRedistributeSegments:
    def test_text_changes_timing_never_does(self) -> None:
        segments = (
            TranscriptionSegment(start_seconds=0.0, end_seconds=100.0, text="एक दो तीन"),
            TranscriptionSegment(start_seconds=95.0, end_seconds=195.0, text="चार पाँच"),
        )
        punctuated = f"एक दो, तीन{DANDA} चार पाँच{DANDA}"
        rebuilt = redistribute_segments(segments, punctuated)
        assert [s.text for s in rebuilt] == [f"एक दो, तीन{DANDA}", f"चार पाँच{DANDA}"]
        assert [(s.start_seconds, s.end_seconds) for s in rebuilt] == [(0.0, 100.0), (95.0, 195.0)]
        # The M19 verbose_json law survives the stage:
        assert " ".join(s.text for s in rebuilt) == punctuated

    def test_word_count_drift_is_refused(self) -> None:
        segments = (TranscriptionSegment(start_seconds=0.0, end_seconds=1.0, text="एक दो"),)
        with pytest.raises(PunctuationStageError):
            redistribute_segments(segments, f"एक{DANDA}")


# ── Pinned identity ──────────────────────────────────────────────────────


class TestArtifactPins:
    def test_the_spec_is_pinned_and_seeded_never_downloaded(self) -> None:
        assert PUNCTUATION_FILES.artifact == PUNCTUATION_ARTIFACT == "punct-cap-seg-47"
        assert PUNCTUATION_FILES.version == 1
        names = {file.filename: file for file in PUNCTUATION_FILES.files}
        assert set(names) == {ONNX_FILENAME, SPM_FILENAME, CONFIG_FILENAME}
        assert (
            names[ONNX_FILENAME].sha256
            == "640d91c06b7cc5b3e065c12a7097188378aad3bc11568ff1d72c4c0a2acb0df4"
        )
        assert (
            names[SPM_FILENAME].sha256
            == "1bc15b6e5fd80dfac9999582ce3efcad2ac1f7cf4e0e9769b329f5de9ca5af47"
        )
        assert (
            names[CONFIG_FILENAME].sha256
            == "30eb8e05fcea3865828ab73f41fbba21dd7faf127a61950a706af9156f5b84f2"
        )
        for file in PUNCTUATION_FILES.files:
            assert ".invalid/" in file.url  # distribution is seeding, by design

    def test_the_v1_mark_scope_is_exactly_danda_comma_question(self) -> None:
        assert SUPPORTED_MARKS == (DANDA, ",", "?")
        assert len(POST_LABELS) == 16
        assert set(POST_LABEL_MAP) == set(POST_LABELS)
        produced = {mark for mark in POST_LABEL_MAP.values() if mark is not None}
        assert produced == set(SUPPORTED_MARKS)
        # The model has no "!" label, and "." is out of the v1 scope — the
        # map must never invent either.
        assert "!" not in POST_LABELS
        assert POST_LABEL_MAP["."] is None


# ── Gating + fail-open (seam level; no model needed) ─────────────────────


class _BareRestorer(PunctuationRestorer):
    """The gating/fail-open surface without weights: __init__ skipped by
    design — these laws must hold independently of any loaded model."""

    def __init__(self, languages: tuple[str, ...] = ("hi", "hi-IN")) -> None:
        self._languages = frozenset(tag.casefold() for tag in languages)
        self._timeout_seconds = 1.0


class _ExplodingRestorer(_BareRestorer):
    def restore(self, result: TranscriptionResult) -> TranscriptionResult:
        msg = "boom /models/secret/path qwen llama"
        raise RuntimeError(msg)


class _RewritingRestorer(_BareRestorer):
    def restore(self, result: TranscriptionResult) -> TranscriptionResult:
        marks: list[list[str]] = [[] for _ in range(len(result.text.split()) + 1)]
        marks[-1] = [DANDA]
        punctuated = apply_marks(result.text, marks)
        return TranscriptionResult(
            text=punctuated,
            language=result.language,
            duration_seconds=result.duration_seconds,
            segments=redistribute_segments(result.segments, punctuated),
            raw_text=result.text,
        )


def _result(text: str = "नमस्ते दुनिया") -> TranscriptionResult:
    return TranscriptionResult(
        text=text,
        language="hi",
        duration_seconds=1.0,
        segments=(TranscriptionSegment(start_seconds=0.0, end_seconds=1.0, text=text),),
    )


class TestGatingAndFailOpen:
    def test_the_stage_follows_the_resolved_route_never_auto(self) -> None:
        restorer = _BareRestorer()
        assert restorer.applies_to("hi")
        assert restorer.applies_to("hi-IN")
        assert not restorer.applies_to("en")
        assert not restorer.applies_to("ar")
        assert not restorer.applies_to(None)  # auto: no language, no stage

    def test_a_non_whitelisted_language_passes_through_untouched(self) -> None:
        outcome = _RewritingRestorer().restore_safely(_result(), "en")
        assert not outcome.applied
        assert outcome.result.text == "नमस्ते दुनिया"
        assert outcome.result.raw_text is None

    def test_any_stage_failure_serves_the_raw_transcript(self) -> None:
        outcome = _ExplodingRestorer().restore_safely(_result(), "hi")
        assert not outcome.applied
        assert outcome.result.text == "नमस्ते दुनिया"
        assert outcome.result.raw_text is None

    def test_success_carries_raw_text_for_provenance(self) -> None:
        outcome = _RewritingRestorer().restore_safely(_result(), "hi")
        assert outcome.applied
        assert outcome.result.text == f"नमस्ते दुनिया{DANDA}"
        assert outcome.result.raw_text == "नमस्ते दुनिया"
        assert " ".join(s.text for s in outcome.result.segments) == outcome.result.text


# ── Route wiring (reference engine + stub stage) ─────────────────────────


def post_audio(client: TestClient, payload: bytes, *, params: str = "{}") -> object:
    return client.post(
        "/v1/transcribe",
        files={"file": ("audio.wav", payload, "audio/wav")},
        data={"params": params},
    )


class TestRouteWiring:
    def test_the_stage_rides_the_response_and_the_timing(self) -> None:
        app = create_app(Settings(console_logs=True, max_concurrency=1, max_queue=1))
        with TestClient(app) as client:
            app.state.punctuator = _RewritingRestorer()
            response = client.post(
                "/v1/transcribe",
                files={"file": ("audio.wav", wav_bytes(duration_seconds=0.5), "audio/wav")},
                data={"params": '{"language": "hi"}'},
            )
            assert response.status_code == 200
            envelope = RuntimeResponse[TranscriptionResult].model_validate_json(response.text)
            assert envelope.output.text.endswith(DANDA)
            assert envelope.output.raw_text is not None
            assert envelope.output.text.rstrip(DANDA).split() == envelope.output.raw_text.split()
            assert "punctuation" in envelope.timing.stages
            assert " ".join(s.text for s in envelope.output.segments) == envelope.output.text

    def test_a_broken_stage_never_breaks_transcription(self) -> None:
        app = create_app(Settings(console_logs=True, max_concurrency=1, max_queue=1))
        with TestClient(app) as client:
            app.state.punctuator = _ExplodingRestorer()
            response = client.post(
                "/v1/transcribe",
                files={"file": ("audio.wav", wav_bytes(duration_seconds=0.5), "audio/wav")},
                data={"params": '{"language": "hi"}'},
            )
            assert response.status_code == 200
            envelope = RuntimeResponse[TranscriptionResult].model_validate_json(response.text)
            assert envelope.output.text != ""
            assert envelope.output.raw_text is None

    def test_silence_never_reaches_the_stage(self) -> None:
        app = create_app(Settings(console_logs=True, max_concurrency=1, max_queue=1))
        with TestClient(app) as client:
            app.state.punctuator = _RewritingRestorer()
            response = client.post(
                "/v1/transcribe",
                files={
                    "file": (
                        "audio.wav",
                        wav_bytes(duration_seconds=1.0, tone_hz=None),
                        "audio/wav",
                    )
                },
                data={"params": '{"language": "hi"}'},
            )
            envelope = RuntimeResponse[TranscriptionResult].model_validate_json(response.text)
            assert envelope.output.text == ""
            assert envelope.output.raw_text is None
            assert "punctuation" not in envelope.timing.stages


# ── Real pinned model (dev machines only; CI skips) ──────────────────────

_LOCAL_ARTIFACT = Path("models/punct-cap-seg-47/v1")
_HAVE_MODEL = (
    (_LOCAL_ARTIFACT / ONNX_FILENAME).exists()
    and importlib.util.find_spec("onnxruntime") is not None
    and importlib.util.find_spec("sentencepiece") is not None
)


@pytest.mark.skipif(not _HAVE_MODEL, reason="seeded punctuation artifact + extra not present")
class TestRealModel:
    def test_the_pinned_model_restores_and_preserves_words(self) -> None:
        restorer = load_punctuation(_LOCAL_ARTIFACT, languages=("hi",), timeout_ms=10_000)
        try:
            for raw in (
                "क्या आप कल ऑफिस आओगे",
                "रोलैंडो मेंडोज़ा ने अपनी M16 राइफल से पर्यटकों के ऊपर फायर किया",
                "मुझे अपना बायोडाटा support@example.com पर भेज दीजिए",
            ):
                outcome: StageOutcome = restorer.restore_safely(_result(raw), "hi")
                assert outcome.applied
                assert invariant_holds(raw, outcome.result.text)
                assert "unk" not in outcome.result.text.casefold()
            question = restorer.restore_safely(_result("क्या आप कल ऑफिस आओगे"), "hi")
            assert question.result.text.endswith("?")
        finally:
            restorer.close()
