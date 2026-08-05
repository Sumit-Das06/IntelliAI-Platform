"""The Evidential Chain, checked where the evidence actually lives.

No route without evidence; no evidence without a versioned corpus; and —
since ADR-0027 Amendment 3 — no promise above `available` without a
versioned dataset the platform owns or has adopted, containing natural
speech in the promoted language.

The *shape* of that is enforced at gateway composition (a `supported`
route cannot be constructed without its citations). Whether the citations
**resolve** is enforced here, because the corpora and the records are on
this side of the boundary and the gateway must not read the evaluation
tree at startup. Between them the chain has no gap: a promise that names
nothing fails the build, and a promise that names something imaginary
fails CI.
"""

import json
from pathlib import Path

import pytest

from intelliai_evaluation.dataset import EvalDataset, find_dataset
from intelliai_evaluation.resolution import ResolvedServing, load_manifest
from intelliai_evaluation.results import EvalRun

MANIFEST = Path("ml/evaluation/manifests/resolution.json")
CAPABILITY_TREES = {
    "transcription": Path("ml/evaluation/stt"),
    "speech_synthesis": Path("ml/evaluation/tts"),
}
CORPUS_DIRS = ("datasets", "corpora")


def promised_routes() -> list[tuple[str, str, ResolvedServing]]:
    """Every (model, capability, route) the platform currently promises."""
    manifest = load_manifest(MANIFEST)
    return [
        (entry.public_model, entry.capability, route)
        for entry in manifest.models
        for route in entry.routes
        if route.status == "supported"
    ]


def _corpus(capability: str, name: str, version: int) -> EvalDataset | dict[str, object]:
    """The cited corpus, from whichever tree its capability keeps them in."""
    tree = CAPABILITY_TREES[capability]
    for directory in CORPUS_DIRS:
        path = tree / directory
        if not path.exists():
            continue
        try:
            return find_dataset(path, name, version)
        except (FileNotFoundError, ValueError):
            # Synthesis corpora are a different schema in the same role;
            # read them as documents rather than pretending they are not
            # corpora.
            for candidate in sorted(path.glob("*.json")):
                document: dict[str, object] = json.loads(candidate.read_text(encoding="utf-8"))
                if document.get("name") == name and document.get("version") == version:
                    return document
    msg = f"no corpus {name}@v{version} under {tree}"
    raise FileNotFoundError(msg)


def test_the_platform_promises_something() -> None:
    # A guard on the guard: if the manifest ever stops carrying promises,
    # every test below would pass vacuously.
    assert promised_routes(), "no supported routes found — the checks below prove nothing"


@pytest.mark.parametrize(
    ("model", "capability", "route"),
    [(m, c, r) for m, c, r in promised_routes()],
    ids=[f"{m}/{r.language}" for m, _, r in promised_routes()],
)
class TestEveryPromiseIsBacked:
    def test_it_cites_evidence_at_all(
        self, model: str, capability: str, route: ResolvedServing
    ) -> None:
        assert route.evidence is not None, f"{model}/{route.language} promises without citing"

    def test_its_corpus_is_a_released_version_we_can_open(
        self, model: str, capability: str, route: ResolvedServing
    ) -> None:
        assert route.evidence is not None
        name, version = route.evidence.corpus_identity
        assert _corpus(capability, name, version) is not None

    def test_its_corpus_is_owned_or_formally_adopted(
        self, model: str, capability: str, route: ResolvedServing
    ) -> None:
        assert route.evidence is not None
        assert route.evidence.corpus_ownership in {"owned", "adopted"}

    def test_its_corpus_contains_natural_speech_in_the_promised_language(
        self, model: str, capability: str, route: ResolvedServing
    ) -> None:
        # ADR-0027 Amendment 3, the whole point: evidence quality is
        # bounded by dataset quality. A promise resting on a corpus with
        # no material in its own language is a number about nothing.
        assert route.evidence is not None
        name, version = route.evidence.corpus_identity
        corpus = _corpus(capability, name, version)
        if isinstance(corpus, EvalDataset):
            material = [
                clip
                for clip in corpus.clips
                if clip.language == route.language
                and clip.synthetic is None
                and clip.reference_text
            ]
        else:  # synthesis corpora: cases carry the language, text is the material
            cases = corpus.get("cases", [])
            assert isinstance(cases, list)
            material = [case for case in cases if case.get("language") == route.language]
        assert material, (
            f"{model} promises {route.language!r} on {name}@v{version}, which contains "
            f"no natural {route.language!r} material"
        )


def test_a_production_benchmark_citation_resolves_to_a_committed_ladder() -> None:
    """The gap the ladder had: `production_benchmark` was stored, echoed
    into the manifest, non-empty-checked — and never resolved. A
    `supported` promotion could therefore cite a production benchmark
    that did not exist, while every gate passed green.

    Closed here (B8): the citation names a committed baseline DOCUMENT in
    the capability's benchmarks tree, and that document must identify a
    raw ladder record beside it that parses. Names, not paths: the
    citation is the document's identity, and the document is the named
    baseline the methodology says citations quote.
    """
    from intelliai_evaluation.evidence import BenchReport, TtsBenchReport

    for model, capability, route in promised_routes():
        assert route.evidence is not None
        citation = route.evidence.production_benchmark
        document_path = CAPABILITY_TREES[capability] / "benchmarks" / f"{citation}.md"
        assert document_path.exists(), (
            f"{model}/{route.language} cites production benchmark {citation!r}, "
            f"and no committed baseline document carries that name"
        )
        text = document_path.read_text(encoding="utf-8")
        raw_names = [
            token
            for token in text.replace("(", " ").replace(")", " ").split()
            if token.endswith(".json")
        ]
        assert raw_names, (
            f"baseline document {citation!r} identifies no raw ladder record; "
            "a named baseline must link the JSON it renders"
        )
        raw_path = document_path.parent / raw_names[0].split("/")[-1].split("]")[-1]
        assert raw_path.exists(), f"{citation!r} links {raw_names[0]}, which is not committed"
        document = json.loads(raw_path.read_text(encoding="utf-8"))
        ladder = BenchReport if "clip" in document else TtsBenchReport
        assert ladder.model_validate(document).levels, (
            f"the raw ladder behind {citation!r} does not parse as a production benchmark"
        )


def test_a_quality_baseline_citation_names_a_committed_record() -> None:
    """Every promise's quality baseline exists as a record, by NAME.

    Names, not paths: `SPEECH_EVALUATION.md` says citations quote
    baselines and never filenames, precisely so a file can move without
    breaking the chain.
    """
    for model, capability, route in promised_routes():
        assert route.evidence is not None
        wanted = route.evidence.quality_baseline
        found = False
        for path in sorted((CAPABILITY_TREES[capability] / "results").glob("*.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            if document.get("baseline_name") == wanted:
                found = True
                break
            identity = document.get("identity")
            if isinstance(identity, dict) and identity.get("benchmark") == wanted:
                found = True
                break
        assert found, f"{model}/{route.language} cites baseline {wanted!r}, which no record claims"


def test_the_english_promise_rests_on_the_record_this_milestone_produced() -> None:
    # The chain, walked once end to end by hand, so a reader can see it.
    (route,) = [r for m, _, r in promised_routes() if m == "intelliai-stt" and r.language == "en"]
    assert route.evidence is not None
    baseline = EvalRun.model_validate_json(
        Path("ml/evaluation/stt/results/2026-08-05-intelliai-stt-en.json").read_text(
            encoding="utf-8"
        )
    )
    assert baseline.identity is not None
    assert baseline.identity.benchmark == route.evidence.quality_baseline
    assert f"{baseline.identity.dataset}@v{baseline.identity.dataset_version}" == (
        route.evidence.corpus
    )
    assert baseline.identity.artifact == route.artifact
    assert baseline.coverage is not None
    assert baseline.coverage.is_quality_claim is True
