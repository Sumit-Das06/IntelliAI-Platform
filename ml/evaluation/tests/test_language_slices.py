"""Language-sliced evaluation, and the committed multilingual evidence."""

from pathlib import Path

import pytest

from intelliai_evaluation.dataset import find_dataset, load_dataset
from intelliai_evaluation.results import ClipResult, EvalRun
from intelliai_evaluation.runner import language_slice, slice_coverage

DATASETS = Path("ml/evaluation/stt/datasets")
RESULTS = Path("ml/evaluation/stt/results")
V2 = DATASETS / "stt-eval-v2.json"


class TestDatasetIdentity:
    def test_a_dataset_is_found_by_identity_not_by_filename(self) -> None:
        # Records cite `name@vN`; a file can be renamed, a release cannot.
        found = find_dataset(DATASETS, "stt-eval-seed", 2)
        assert (found.name, found.version) == ("stt-eval-seed", 2)

    def test_an_unreleased_version_is_a_clear_miss(self) -> None:
        with pytest.raises(FileNotFoundError, match="stt-eval-seed@v99"):
            find_dataset(DATASETS, "stt-eval-seed", 99)

    def test_v1_is_carried_forward_byte_identical_into_v2(self) -> None:
        # An `en` run on v2 is comparable to the v1 baseline only if the
        # clips it shares are the same clips, pin for pin.
        v1 = load_dataset(DATASETS / "stt-eval-v1.json")
        v2 = load_dataset(V2)
        v2_by_id = {clip.id: clip for clip in v2.clips}
        for clip in v1.clips:
            assert v2_by_id[clip.id] == clip

    def test_released_versions_are_never_edited(self) -> None:
        assert load_dataset(DATASETS / "stt-eval-v1.json").version == 1
        assert len(load_dataset(DATASETS / "stt-eval-v1.json").clips) == 4


class TestLanguageSlices:
    def test_a_slice_is_exactly_the_clips_that_declare_its_language(self) -> None:
        dataset = load_dataset(V2)
        assert [clip.id for clip in language_slice(dataset, "hi")] == [
            "hi-silence-10s",
            "hi-tone-440hz-5s",
        ]
        assert [clip.id for clip in language_slice(dataset, "zxx")] == [
            "silence-10s",
            "tone-440hz-5s",
        ]

    def test_a_slice_never_widens_to_include_other_languages(self) -> None:
        # The record's identity says one language; a reader is entitled to
        # believe it, so a `hi` run must not quietly measure `zxx` probes.
        dataset = load_dataset(V2)
        for language in ("en", "hi", "zxx"):
            for clip in language_slice(dataset, language):
                assert clip.language == language

    def test_the_declaration_is_the_experimental_variable(self) -> None:
        # The same deterministic audio appears under `en` and under `hi`,
        # so the effect of the DECLARATION is measurable with no corpus.
        dataset = load_dataset(V2)
        english = {c.id: c.synthetic for c in language_slice(dataset, "en") if c.synthetic}
        hindi = {c.id: c.synthetic for c in language_slice(dataset, "hi") if c.synthetic}
        assert english["en-silence-10s"] == hindi["hi-silence-10s"]
        assert english["en-tone-440hz-5s"] == hindi["hi-tone-440hz-5s"]


class TestCoverage:
    def _result(self, reference_words: int) -> ClipResult:
        return ClipResult(
            clip_id="x",
            duration_seconds=1.0,
            inference_seconds=0.1,
            substitutions=0,
            insertions=0,
            deletions=0,
            reference_words=reference_words,
            hypothesis_words=0,
            hypothesis_text="",
        )

    def test_the_hindi_slice_declares_that_it_holds_no_natural_speech(self) -> None:
        dataset = load_dataset(V2)
        clips = language_slice(dataset, "hi")
        coverage = slice_coverage(clips, [self._result(0) for _ in clips])
        assert coverage.natural_speech_clips == 0
        assert coverage.is_quality_claim is False

    def test_the_english_slice_declares_that_it_does(self) -> None:
        dataset = load_dataset(V2)
        clips = language_slice(dataset, "en")
        coverage = slice_coverage(clips, [self._result(22) for _ in clips])
        assert coverage.natural_speech_clips == 2
        assert coverage.is_quality_claim is True


class TestCommittedEvidence:
    """The records this milestone produced, read back as a future reader would."""

    def _run(self, name: str) -> EvalRun:
        return EvalRun.model_validate_json((RESULTS / name).read_text(encoding="utf-8"))

    def test_every_new_record_carries_a_complete_identity(self) -> None:
        for name in ("2026-08-05-intelliai-stt-en.json", "2026-08-05-intelliai-stt-hi.json"):
            identity = self._run(name).identity
            assert identity is not None
            assert identity.public_model == "intelliai-stt"
            assert identity.artifact == "whisper-small"
            assert identity.deployment == "stt-runtime"
            assert identity.dataset_version == 2
            assert identity.benchmark is not None

    def test_the_english_slice_reproduces_the_m2_baseline(self) -> None:
        english = self._run("2026-08-05-intelliai-stt-en.json")
        assert english.overall_wer == 0.0  # identical to the M2 measurement
        assert english.hallucinated_words_total == 0

    def test_the_hindi_record_is_honest_about_what_it_is_not(self) -> None:
        hindi = self._run("2026-08-05-intelliai-stt-hi.json")
        assert hindi.overall_wer is None  # no references: no word error rate
        assert hindi.coverage is not None
        assert hindi.coverage.natural_speech_clips == 0
        assert hindi.coverage.is_quality_claim is False
        assert hindi.summary()["is_quality_claim"] is False

    def test_records_written_before_identity_existed_still_parse(self) -> None:
        # The append-only ledger's whole point: old evidence stays readable.
        legacy = self._run("2026-08-02-whisper-small.json")
        assert legacy.identity is None
        assert legacy.overall_wer == 0.0
