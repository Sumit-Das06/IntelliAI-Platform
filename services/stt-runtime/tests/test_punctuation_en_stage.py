"""The M50 English punctuation stage: the M30 laws on a separate flag.

Word-copy law (SHARED core, imported from the M30 module — never
reimplemented), fail-open law, route-resolved gating, pinned INT8
identity, and STRICT separation from the Hindi stage: flag OFF by
default, English languages only, Hindi defaults untouched. Real-model
behavior runs only where the seeded artifact exists (dev machines);
CI proves the laws through the pure core and the seams.
"""

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
    PunctuationStageError,
    apply_marks,
    invariant_holds,
    redistribute_segments,
)
from intelliai_stt_runtime.engines.punctuation_en import (
    EN_LABEL_MAP,
    EN_POST_LABELS,
    EN_SUPPORTED_MARKS,
    ONNX_EN_FILENAME,
    PROVENANCE_FILENAME,
    PUNCTUATION_EN_ARTIFACT,
    PUNCTUATION_EN_FILES,
    SPM_EN_FILENAME,
    EnPunctuationRestorer,
    EnStageOutcome,
    load_punctuation_en,
)
from intelliai_stt_runtime.main import create_app

ARTIFACT_DIR = Path(__file__).resolve().parents[3] / "models/punct-en-kredor/v1"


# ── Flag + configuration separation ──────────────────────────────────────


class TestConfiguration:
    def test_the_english_flag_defaults_off(self) -> None:
        settings = Settings()
        assert settings.punctuation_en_enabled is False

    def test_the_language_lists_stay_separate(self) -> None:
        settings = Settings()
        assert settings.punctuation_en_languages == "en,en-US,en-IN"
        # The Hindi stage's configuration is UNCHANGED by M50.
        assert settings.punctuation_enabled is False
        assert settings.punctuation_languages == "hi,hi-IN"

    def test_off_means_no_stage_object_and_disabled_readiness(self) -> None:
        app = create_app(Settings(console_logs=True, max_concurrency=1, max_queue=1))
        with TestClient(app) as client:
            assert app.state.punctuator_en is None
            ready = client.get("/health/ready").json()
            assert ready["punctuation_en"] == "disabled"
            assert ready["punctuation"] == "disabled"


# ── Pinned identity ──────────────────────────────────────────────────────


class TestArtifactPins:
    def test_the_spec_is_pinned_and_seeded_never_downloaded(self) -> None:
        assert PUNCTUATION_EN_FILES.artifact == PUNCTUATION_EN_ARTIFACT == "punct-en-kredor"
        assert PUNCTUATION_EN_FILES.version == 1
        names = {file.filename: file for file in PUNCTUATION_EN_FILES.files}
        assert set(names) == {ONNX_EN_FILENAME, SPM_EN_FILENAME, PROVENANCE_FILENAME}
        assert (
            names[ONNX_EN_FILENAME].sha256
            == "b0d8d68ca907012e832282920c43ce8342c7920022ec9e9c125498de9478a925"
        )
        assert (
            names[SPM_EN_FILENAME].sha256
            == "cfc8146abe2a0488e9e2a0c56de7952f7c11ab059eca145a0a727afce0db2865"
        )
        assert (
            names[PROVENANCE_FILENAME].sha256
            == "bb74cc2440f342a69e3cbec427f7627769fd39abad6f7f1b3a1fbc72402374c3"
        )
        for file in PUNCTUATION_EN_FILES.files:
            assert ".invalid/" in file.url  # distribution is seeding, by design

    def test_the_v1_scope_is_exactly_period_comma_question(self) -> None:
        assert EN_SUPPORTED_MARKS == (".", ",", "?")
        assert EN_POST_LABELS == ("0", ".", ",", "?", "-", ":")
        assert set(EN_LABEL_MAP) == set(EN_POST_LABELS)
        produced = {mark for mark in EN_LABEL_MAP.values() if mark is not None}
        assert produced == set(EN_SUPPORTED_MARKS)
        # "-" and ":" exist in the model but are OUT of the v1 contract.
        assert EN_LABEL_MAP["-"] is None
        assert EN_LABEL_MAP[":"] is None

    def test_a_drifted_provenance_refuses_to_load(self, tmp_path: Path) -> None:
        (tmp_path / PROVENANCE_FILENAME).write_text("{}", encoding="utf-8")
        with pytest.raises(PunctuationStageError):
            EnPunctuationRestorer(tmp_path, languages=("en",), timeout_ms=1000.0)


# ── The shared word-copy core, under the ENGLISH mark scope ─────────────


class TestWordCopyUnderEnglishScope:
    def test_english_marks_append_and_words_survive(self) -> None:
        text = "hello my name is Sumit how are you"
        n = len(text.split())
        marks: list[list[str]] = [[] for _ in range(n + 1)]
        marks[5] = ["."]  # after "Sumit"
        marks[n] = ["?"]
        out = apply_marks(text, marks, allowed=EN_SUPPORTED_MARKS)
        assert out == "hello my name is Sumit. how are you?"
        assert invariant_holds(text, out)

    def test_edge_tokens_survive_untouched(self) -> None:
        cases = [
            "call me at +91-9876543210 tomorrow",
            "I bought it for $49.99 yesterday",
            "email me at test@example.com today",
            "visit example.com and check version 2.5",
            "Mr Smith called at 10 a.m. sharp",
            "OpenAI NVIDIA PostgreSQL QwikCart IntelliAI",
            "the pH and GMT and M16 readings",
        ]
        for text in cases:
            n = len(text.split())
            marks: list[list[str]] = [[] for _ in range(n + 1)]
            marks[-1] = ["."]
            out = apply_marks(text, marks, allowed=EN_SUPPORTED_MARKS)
            assert invariant_holds(text, out), text
            assert out.rsplit(".", 1)[0].split() == text.split()

    def test_marks_outside_the_english_scope_are_refused(self) -> None:
        for bad in ("!", ";", ":", "-", "।"):
            with pytest.raises(PunctuationStageError):
                apply_marks("one", [[], [bad]], allowed=EN_SUPPORTED_MARKS)

    def test_the_hindi_scope_is_unchanged_by_the_new_parameter(self) -> None:
        # Default `allowed` is still the Hindi v1 scope: "." refused.
        with pytest.raises(PunctuationStageError):
            apply_marks("एक", [[], ["."]])


# ── Gating + fail-open (seam level; no model needed) ─────────────────────


class _BareEnRestorer(EnPunctuationRestorer):
    """The gating/fail-open surface without weights: __init__ skipped by
    design — these laws must hold independently of any loaded model."""

    def __init__(self, languages: tuple[str, ...] = ("en", "en-US", "en-IN")) -> None:
        self._languages = frozenset(tag.casefold() for tag in languages)
        self._timeout_seconds = 1.0


class _ExplodingEnRestorer(_BareEnRestorer):
    def restore(self, result: TranscriptionResult) -> TranscriptionResult:
        msg = "boom /models/secret/path kredor onnx"
        raise RuntimeError(msg)


class _RewritingEnRestorer(_BareEnRestorer):
    def restore(self, result: TranscriptionResult) -> TranscriptionResult:
        marks: list[list[str]] = [[] for _ in range(len(result.text.split()) + 1)]
        marks[-1] = ["."]
        punctuated = apply_marks(result.text, marks, allowed=EN_SUPPORTED_MARKS)
        return TranscriptionResult(
            text=punctuated,
            language=result.language,
            duration_seconds=result.duration_seconds,
            segments=redistribute_segments(result.segments, punctuated),
            raw_text=result.text,
        )


class _WordRewritingEnRestorer(_BareEnRestorer):
    """A malformed stage that CHANGES a word — restore_safely must bury it.

    (The real engine cannot produce this — apply_marks copies tokens —
    but the seam must reject even a hypothetically broken implementation
    the moment its output violates the invariant.)
    """

    def restore(self, result: TranscriptionResult) -> TranscriptionResult:
        broken = result.text.replace("hello", "hi") + "."
        if not invariant_holds(result.text, broken):
            msg = "word-preservation invariant violated"
            raise PunctuationStageError(msg)
        return result


def _result(text: str = "hello world") -> TranscriptionResult:
    return TranscriptionResult(
        text=text,
        language="en",
        duration_seconds=1.0,
        segments=(TranscriptionSegment(start_seconds=0.0, end_seconds=1.0, text=text),),
    )


class TestGatingAndFailOpen:
    def test_the_stage_follows_the_resolved_route_never_auto(self) -> None:
        restorer = _BareEnRestorer()
        assert restorer.applies_to("en")
        assert restorer.applies_to("en-US")
        assert restorer.applies_to("en-IN")
        assert not restorer.applies_to("hi")
        assert not restorer.applies_to("hi-IN")
        assert not restorer.applies_to("ar")
        assert not restorer.applies_to(None)  # auto: no language, no stage

    def test_a_non_whitelisted_language_passes_through_untouched(self) -> None:
        outcome = _RewritingEnRestorer().restore_safely(_result(), "hi")
        assert not outcome.applied
        assert outcome.result.text == "hello world"
        assert outcome.result.raw_text is None

    def test_any_stage_failure_serves_the_raw_transcript(self) -> None:
        outcome = _ExplodingEnRestorer().restore_safely(_result(), "en")
        assert not outcome.applied
        assert outcome.result.text == "hello world"
        assert outcome.result.raw_text is None

    def test_an_invariant_violation_is_buried_by_the_seam(self) -> None:
        outcome = _WordRewritingEnRestorer().restore_safely(_result(), "en")
        assert not outcome.applied
        assert outcome.result.text == "hello world"

    def test_success_carries_raw_text_for_provenance(self) -> None:
        outcome = _RewritingEnRestorer().restore_safely(_result(), "en")
        assert isinstance(outcome, EnStageOutcome)
        assert outcome.applied
        assert outcome.result.text == "hello world."
        assert outcome.result.raw_text == "hello world"
        assert " ".join(s.text for s in outcome.result.segments) == outcome.result.text


# ── Route wiring (reference engine + stub stage) ─────────────────────────


class TestRouteWiring:
    def test_the_english_stage_rides_the_response_and_the_timing(self) -> None:
        app = create_app(Settings(console_logs=True, max_concurrency=1, max_queue=1))
        with TestClient(app) as client:
            app.state.punctuator_en = _RewritingEnRestorer()
            response = client.post(
                "/v1/transcribe",
                files={"file": ("audio.wav", wav_bytes(duration_seconds=0.5), "audio/wav")},
                data={"params": '{"language": "en"}'},
            )
            assert response.status_code == 200
            envelope = RuntimeResponse[TranscriptionResult].model_validate_json(response.text)
            assert envelope.output.text.endswith(".")
            assert envelope.output.raw_text is not None
            assert envelope.output.text.rstrip(".").split() == envelope.output.raw_text.split()
            assert "punctuation_en" in envelope.timing.stages

    def test_a_broken_english_stage_never_breaks_transcription(self) -> None:
        app = create_app(Settings(console_logs=True, max_concurrency=1, max_queue=1))
        with TestClient(app) as client:
            app.state.punctuator_en = _ExplodingEnRestorer()
            response = client.post(
                "/v1/transcribe",
                files={"file": ("audio.wav", wav_bytes(duration_seconds=0.5), "audio/wav")},
                data={"params": '{"language": "en"}'},
            )
            assert response.status_code == 200
            envelope = RuntimeResponse[TranscriptionResult].model_validate_json(response.text)
            assert envelope.output.text != ""
            assert envelope.output.raw_text is None

    def test_a_hindi_request_never_reaches_the_english_stage(self) -> None:
        app = create_app(Settings(console_logs=True, max_concurrency=1, max_queue=1))
        with TestClient(app) as client:
            app.state.punctuator_en = _RewritingEnRestorer()
            response = client.post(
                "/v1/transcribe",
                files={"file": ("audio.wav", wav_bytes(duration_seconds=0.5), "audio/wav")},
                data={"params": '{"language": "hi"}'},
            )
            assert response.status_code == 200
            envelope = RuntimeResponse[TranscriptionResult].model_validate_json(response.text)
            assert not envelope.output.text.endswith(".")
            assert "punctuation_en" not in envelope.timing.stages or (
                envelope.output.raw_text is None
            )


# ── Real INT8 model (dev machines with the seeded artifact only) ────────


@pytest.mark.skipif(
    not (ARTIFACT_DIR / ONNX_EN_FILENAME).exists(),
    reason="seeded punct-en-kredor artifact not present",
)
class TestRealModel:
    def test_loads_verifies_and_punctuates_with_words_verbatim(self) -> None:
        restorer = load_punctuation_en(ARTIFACT_DIR, languages=("en",), timeout_ms=10000.0)
        try:
            text = "hello my name is sumit how are you"
            outcome = restorer.restore_safely(_result(text), "en")
            assert outcome.applied
            assert invariant_holds(text, outcome.result.text)
            added = [c for c in outcome.result.text if not c.isalnum() and c != " "]
            assert added, "the real model should add at least one mark"
            assert set(added) <= set(EN_SUPPORTED_MARKS)
            assert outcome.result.raw_text == text
        finally:
            restorer.close()
