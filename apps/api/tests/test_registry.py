"""Registry V1.5: resolution, serving routes, the ladder, and the gates."""

from datetime import date

import pytest
from pydantic import ValidationError

from intelliai_api.core.errors import ErrorType
from intelliai_api.registry import (
    ADMITTED_SELECTOR_DIMENSIONS,
    ArtifactRecord,
    CorpusOwnership,
    LanguageEvidence,
    LanguageNotSupportedError,
    LanguageStatus,
    LicenseVerdict,
    ModelNotFoundError,
    PublicModelRecord,
    PublicVoiceRecord,
    Registry,
    Resolution,
    RouteSelector,
    RouteStage,
    ServingRoute,
    default_registry,
    normalize_language,
)
from intelliai_runtime_contract import Capability

MIT = LicenseVerdict(
    license="MIT",
    commercial_use=True,
    verified_on=date(2026, 7, 31),
    source="https://example.com/license",
)

NON_COMMERCIAL = LicenseVerdict(
    license="CC-BY-NC-4.0",
    commercial_use=False,
    verified_on=date(2026, 7, 31),
    source="https://example.com/license",
)

# A commercially clean model reached through a contaminated path — the
# shape of the real Hindi TTS gate (a GPL phonemizer, not a model).
GPL_PATH = LicenseVerdict(
    license="GPL-3.0-only",
    commercial_use=False,
    verified_on=date(2026, 8, 4),
    source="https://example.com/phonemizer",
    covers="weights (Apache-2.0) plus the Hindi grapheme-to-phoneme dependency",
)


def artifact(**overrides: object) -> ArtifactRecord:
    fields: dict[str, object] = {
        "id": "whisper-small",
        "version": 1,
        "capability": Capability.TRANSCRIPTION,
        "provenance": "test provenance",
        "license": MIT,
    }
    fields.update(overrides)
    return ArtifactRecord.model_validate(fields)


def model(**overrides: object) -> PublicModelRecord:
    fields: dict[str, object] = {
        "id": "intelliai-stt",
        "capability": Capability.TRANSCRIPTION,
        "service": "stt-runtime",
        "artifact_id": "whisper-small",
        "released": date(2026, 8, 2),
    }
    fields.update(overrides)
    return PublicModelRecord.model_validate(fields)


class TestResolution:
    def test_resolves_to_capability_service_and_artifact(self) -> None:
        registry = Registry(artifacts=[artifact()], models=[model()])
        resolution = registry.resolve("intelliai-stt")
        assert resolution == Resolution(
            public_model_id="intelliai-stt",
            capability=Capability.TRANSCRIPTION,
            service="stt-runtime",
            artifact=artifact(),
        )

    def test_unknown_model_raises_not_found_with_public_error_shape(self) -> None:
        registry = Registry(artifacts=[artifact()], models=[model()])
        with pytest.raises(ModelNotFoundError) as exc_info:
            registry.resolve("gpt-4o")
        err = exc_info.value
        assert err.error_type is ErrorType.NOT_FOUND
        assert err.status_code == 404
        assert err.code == "model_not_found"
        assert err.param == "model"
        assert "gpt-4o" in err.message
        assert not err.retryable

    def test_list_models_backs_v1_models_endpoint(self) -> None:
        registry = Registry(artifacts=[artifact()], models=[model()])
        assert [m.id for m in registry.list_models()] == ["intelliai-stt"]


class TestLicenseGate:
    def test_recording_a_non_commercial_artifact_is_legal(self) -> None:
        # Records state facts; the gate is at composition, not at the record.
        assert artifact(license=NON_COMMERCIAL).license.commercial_use is False

    def test_routing_to_a_non_commercial_artifact_cannot_compose(self) -> None:
        with pytest.raises(ValueError, match="commercial-use"):
            Registry(artifacts=[artifact(license=NON_COMMERCIAL)], models=[model()])

    def test_unrouted_non_commercial_artifact_may_exist(self) -> None:
        # An artifact under evaluation can sit in the catalog unrouted.
        registry = Registry(
            artifacts=[artifact(), artifact(id="research-only", license=NON_COMMERCIAL)],
            models=[model()],
        )
        assert registry.resolve("intelliai-stt").artifact.id == "whisper-small"


class TestCatalogIntegrity:
    def test_route_to_unknown_artifact_cannot_compose(self) -> None:
        with pytest.raises(ValueError, match="unknown artifact"):
            Registry(artifacts=[artifact()], models=[model(artifact_id="missing")])

    def test_route_to_wrong_capability_artifact_cannot_compose(self) -> None:
        # Promised at M2 step 2: with a single Capability member this
        # mismatch was unconstructible; SPEECH_SYNTHESIS makes the guard
        # finally provable.
        tts_artifact = artifact(id="synthesis-model", capability=Capability.SPEECH_SYNTHESIS)
        with pytest.raises(ValueError, match="different capability"):
            Registry(artifacts=[tts_artifact], models=[model(artifact_id="synthesis-model")])

    def test_duplicate_ids_cannot_compose(self) -> None:
        with pytest.raises(ValueError, match="duplicate artifact"):
            Registry(artifacts=[artifact(), artifact()], models=[model()])
        with pytest.raises(ValueError, match="duplicate public model"):
            Registry(artifacts=[artifact()], models=[model(), model()])

    def test_records_are_frozen_and_reject_unknown_fields(self) -> None:
        record = artifact()
        with pytest.raises(ValidationError):
            record.id = "other"  # type: ignore[misc]
        with pytest.raises(ValidationError):
            artifact(precision="int8")  # build concern — never identity (ADR-0015)


def voice(**overrides: object) -> PublicVoiceRecord:
    fields: dict[str, object] = {
        "id": "reference-alto",
        "model": "intelliai-stt",
        "languages": ("en",),
        "released": date(2026, 8, 3),
    }
    fields.update(overrides)
    return PublicVoiceRecord.model_validate(fields)


class TestVoiceCatalog:
    def test_voices_list_and_filter_by_model(self) -> None:
        registry = Registry(artifacts=[artifact()], models=[model()], voices=[voice()])
        assert [v.id for v in registry.list_voices()] == ["reference-alto"]
        assert registry.list_voices("intelliai-stt")[0].id == "reference-alto"
        assert registry.list_voices("intelliai-other") == ()

    def test_voice_for_unknown_model_cannot_compose(self) -> None:
        with pytest.raises(ValueError, match="unknown model"):
            Registry(
                artifacts=[artifact()],
                models=[model()],
                voices=[voice(model="intelliai-tts-missing")],
            )

    def test_duplicate_voice_ids_cannot_compose(self) -> None:
        with pytest.raises(ValueError, match="duplicate public voice"):
            Registry(artifacts=[artifact()], models=[model()], voices=[voice(), voice()])


class TestDefaultCatalog:
    def test_composes_and_serves_intelliai_stt(self) -> None:
        resolution = default_registry().resolve("intelliai-stt")
        assert resolution.capability is Capability.TRANSCRIPTION
        assert resolution.service == "stt-runtime"
        assert resolution.artifact.id == "whisper-small"

    def test_every_routed_artifact_passed_the_license_gate(self) -> None:
        registry = default_registry()
        for public_model in registry.list_models():
            verdict = registry.resolve(public_model.id).artifact.license
            assert verdict.commercial_use is True
            assert verdict.verified_on <= date(2026, 12, 31)
            assert verdict.source.startswith("https://")

    def test_composes_and_serves_intelliai_tts(self) -> None:
        resolution = default_registry().resolve("intelliai-tts")
        assert resolution.capability is Capability.SPEECH_SYNTHESIS
        assert resolution.service == "tts-runtime"
        assert resolution.artifact.id == "kokoro-82m"
        voice_ids = [v.id for v in default_registry().list_voices("intelliai-tts")]
        assert voice_ids == [
            "english-female",
            "english-male",
            "reference-alto",
            "reference-bass",
        ]

    def test_public_ids_never_leak_engine_names(self) -> None:
        # The product boundary: customers see intelliai-*, never engines.
        for public_model in default_registry().list_models():
            assert public_model.id.startswith("intelliai-")
        # Voice ids follow the same law: never an engine voice token.
        for public_voice in default_registry().list_voices():
            assert not public_voice.id.startswith(("af_", "am_", "bf_", "bm_"))


# ══ Registry V1.5 — serving routes (ADR-0025, ADR-0027) ═════════════════


EVIDENCE = LanguageEvidence(
    corpus="stt-eval-seed@v1",
    corpus_ownership=CorpusOwnership.OWNED,
    quality_baseline="test-baseline",
    production_benchmark="test-benchmark",
    approval="test approval",
    approved_on=date(2026, 8, 4),
)


def route(**overrides: object) -> ServingRoute:
    fields: dict[str, object] = {
        "public_model_id": "intelliai-stt",
        "selector": RouteSelector(language="hi"),
        "status": LanguageStatus.AVAILABLE,
        "artifact_id": "whisper-small",
        "license": MIT,
    }
    fields.update(overrides)
    return ServingRoute.model_validate(fields)


class TestSelectorAdmissionTest:
    """A selector dimension is admissible only if the customer could know
    its value from their own request or their own agreement."""

    def test_selector_carries_exactly_the_admitted_dimensions(self) -> None:
        assert set(RouteSelector.model_fields) == ADMITTED_SELECTOR_DIMENSIONS
        assert set(ADMITTED_SELECTOR_DIMENSIONS) == {"language"}

    def test_operational_dimensions_are_absent(self) -> None:
        # Knowable only from OUR operations, never from the customer:
        # these belong on deployment records (ADR-0015, ADR-0026).
        inadmissible = {"hardware_class", "deployment", "load", "cost", "placement", "gpu"}
        assert not (set(RouteSelector.model_fields) & inadmissible)

    def test_an_inadmissible_dimension_cannot_even_be_constructed(self) -> None:
        with pytest.raises(ValidationError):
            RouteSelector(language="hi", hardware_class="gpu")  # type: ignore[call-arg]

    def test_the_empty_selector_is_the_default_route_not_a_record(self) -> None:
        # One fact, one representation: the default route is the public
        # model's artifact_id and must not be restated as a route.
        with pytest.raises(ValidationError, match="empty route selector"):
            RouteSelector()

    def test_catalog_selectors_must_already_be_normalized(self) -> None:
        # Customers are read tolerantly; our own catalog is not.
        with pytest.raises(ValidationError, match="normalized base subtag"):
            RouteSelector(language="hi-IN")


class TestRouteStrategyBoundary:
    """A route binds one selector to one artifact — binding, never
    coordination. Coordination is a Serving Strategy (Registry V2)."""

    def test_route_record_shape_is_exactly_the_ratified_shape(self) -> None:
        assert set(ServingRoute.model_fields) == {
            "public_model_id",
            "selector",
            "status",
            "artifact_id",
            "deployment",
            "license",
            "evidence",
            "stage",
        }

    def test_no_coordination_surface_anywhere_on_the_record(self) -> None:
        # The failure mode is accretion: fallback_artifact_id, then
        # traffic_percent, then ensemble_weight — each locally reasonable
        # until resolution is no longer a pure function.
        forbidden = ("fallback", "percent", "weight", "split", "cascade", "ensemble", "strategy")
        surface = set(ServingRoute.model_fields) | {n for n in dir(ServingRoute) if n[0] != "_"}
        for name in surface:
            assert not any(word in name.lower() for word in forbidden), name


class TestReservedBindingStages:
    """The stage vocabulary is named now so Registry V2 inherits it; the
    machine is inert until V2 makes it variable."""

    def test_the_vocabulary_exists_in_full(self) -> None:
        assert {stage.value for stage in RouteStage} == {"shadow", "canary", "production"}

    def test_routes_are_fixed_at_production(self) -> None:
        assert route().stage is RouteStage.PRODUCTION

    @pytest.mark.parametrize("stage", [RouteStage.SHADOW, RouteStage.CANARY])
    def test_an_unreserved_stage_is_refused_not_substituted(self, stage: RouteStage) -> None:
        with pytest.raises(ValidationError, match="reserved for Registry V2"):
            route(stage=stage)


class TestLadderObligations:
    """Each rung's obligations are structural: a promise cannot be made
    without its evidence, and a refusal cannot carry a binding."""

    def test_supported_without_evidence_cannot_be_constructed(self) -> None:
        with pytest.raises(ValidationError, match="without evidence references"):
            route(status=LanguageStatus.SUPPORTED)

    def test_supported_with_evidence_composes(self) -> None:
        assert route(status=LanguageStatus.SUPPORTED, evidence=EVIDENCE).evidence == EVIDENCE

    def test_a_served_rung_must_bind_an_artifact(self) -> None:
        with pytest.raises(ValidationError, match="binds no artifact"):
            route(artifact_id=None)

    def test_a_served_rung_must_carry_a_serving_path_verdict(self) -> None:
        with pytest.raises(ValidationError, match="serving-path license verdict"):
            route(license=None)

    def test_a_refused_language_may_not_carry_a_binding(self) -> None:
        with pytest.raises(ValidationError, match="carries a binding"):
            route(status=LanguageStatus.UNAVAILABLE)

    def test_the_lifecycle_cannot_be_skipped(self) -> None:
        # F-M5-1: `supported` requires a production baseline, and a
        # production baseline is unobtainable without having served.
        # The bar forbids the jump; no state machine is needed.
        assert "production_benchmark" in LanguageEvidence.model_fields
        assert "approval" in LanguageEvidence.model_fields
        with pytest.raises(ValidationError):
            LanguageEvidence(
                corpus="stt-eval-seed@v2",
                corpus_ownership=CorpusOwnership.OWNED,
                quality_baseline="q",
                production_benchmark="",  # the rung that proves service happened
                approval="a",
                approved_on=date(2026, 8, 4),
            )


class TestCorpusPrecondition:
    """ADR-0027 Amendment 3: evidence quality is bounded by dataset quality."""

    def test_a_promise_must_declare_how_we_came_by_its_corpus(self) -> None:
        # An adopted corpus carries its licence into every promotion that
        # cites it; an owned one does not. Which applies is recorded.
        assert "corpus_ownership" in LanguageEvidence.model_fields
        with pytest.raises(ValidationError):
            LanguageEvidence.model_validate(
                {
                    "corpus": "stt-eval-seed@v2",
                    "quality_baseline": "q",
                    "production_benchmark": "b",
                    "approval": "a",
                    "approved_on": date(2026, 8, 5),
                }
            )

    @pytest.mark.parametrize("citation", ["stt-eval-seed", "stt-eval-seed@2", "@v2", "seed@vX"])
    def test_an_unversioned_corpus_citation_cannot_be_checked_by_anyone(
        self, citation: str
    ) -> None:
        with pytest.raises(ValidationError, match="not versioned"):
            LanguageEvidence(
                corpus=citation,
                corpus_ownership=CorpusOwnership.OWNED,
                quality_baseline="q",
                production_benchmark="b",
                approval="a",
                approved_on=date(2026, 8, 5),
            )

    def test_both_ownership_stances_exist_and_only_those(self) -> None:
        assert {member.value for member in CorpusOwnership} == {"owned", "adopted"}

    def test_the_shipped_promises_declare_owned_corpora(self) -> None:
        registry = default_registry()
        for model_id in ("intelliai-stt", "intelliai-tts"):
            for serving_route in registry.list_languages(model_id):
                if serving_route.status is LanguageStatus.SUPPORTED:
                    evidence = serving_route.evidence
                    assert evidence is not None
                    assert evidence.corpus_ownership is CorpusOwnership.OWNED
                    assert "@v" in evidence.corpus


class TestSpecificityLaw:
    """The most specific matching selector wins; the default route matches
    everything; a tie is a composition error, never a coin-flip."""

    def _stt(self, *routes: ServingRoute) -> Registry:
        return Registry(artifacts=[artifact()], models=[model()], routes=list(routes))

    def test_a_language_route_beats_the_default_route(self) -> None:
        specialist = artifact(id="hindi-specialist")
        registry = Registry(
            artifacts=[artifact(), specialist],
            models=[model()],
            routes=[route(artifact_id="hindi-specialist")],
        )
        assert registry.resolve("intelliai-stt", language="hi").artifact.id == "hindi-specialist"
        assert registry.resolve("intelliai-stt").artifact.id == "whisper-small"

    def test_an_unrouted_language_rides_the_default_route(self) -> None:
        registry = self._stt(route())
        assert registry.resolve("intelliai-stt", language="fr").artifact.id == "whisper-small"

    def test_two_bindings_on_one_selector_cannot_compose(self) -> None:
        with pytest.raises(ValueError, match="one binding per selector"):
            self._stt(route(), route())

    def test_distinct_languages_are_not_a_tie(self) -> None:
        registry = self._stt(route(), route(selector=RouteSelector(language="ar")))
        assert registry.served_languages("intelliai-stt") == ("hi", "ar")


class TestLanguageNormalization:
    """Routing normalizes to the base subtag; the full tag stays the fact."""

    @pytest.mark.parametrize("declared", ["hi", "hi-IN", "HI", "hi_IN", " hi-Deva-IN "])
    def test_regional_tags_route_as_their_base_subtag(self, declared: str) -> None:
        registry = Registry(artifacts=[artifact()], models=[model()], routes=[route()])
        assert registry.language_status("intelliai-stt", declared) is LanguageStatus.AVAILABLE

    @pytest.mark.parametrize("declared", [None, "", "   "])
    def test_an_absent_declaration_takes_the_default_route(self, declared: str | None) -> None:
        assert normalize_language(declared) is None


class TestRefusal:
    """`unavailable` is refused honestly, naming what is served."""

    def _tts(self) -> Registry:
        tts_artifact = artifact(id="kokoro-82m", capability=Capability.SPEECH_SYNTHESIS)
        tts_model = model(
            id="intelliai-tts",
            capability=Capability.SPEECH_SYNTHESIS,
            service="tts-runtime",
            artifact_id="kokoro-82m",
        )
        return Registry(
            artifacts=[tts_artifact],
            models=[tts_model],
            routes=[
                ServingRoute(
                    public_model_id="intelliai-tts",
                    selector=RouteSelector(language="en"),
                    status=LanguageStatus.SUPPORTED,
                    artifact_id="kokoro-82m",
                    license=MIT,
                    evidence=EVIDENCE,
                ),
                ServingRoute(
                    public_model_id="intelliai-tts",
                    selector=RouteSelector(language="hi"),
                    status=LanguageStatus.UNAVAILABLE,
                ),
            ],
        )

    def test_a_refused_language_raises_the_public_error_shape(self) -> None:
        with pytest.raises(LanguageNotSupportedError) as exc_info:
            self._tts().resolve("intelliai-tts", language="hi-IN")
        err = exc_info.value
        assert err.error_type is ErrorType.INVALID_REQUEST
        assert err.status_code == 400
        assert err.code == "language_not_supported"
        assert err.param == "language"
        assert not err.retryable

    def test_the_refusal_names_what_is_served(self) -> None:
        with pytest.raises(LanguageNotSupportedError, match="en"):
            self._tts().resolve("intelliai-tts", language="hi")
        assert self._tts().served_languages("intelliai-tts") == ("en",)

    def test_a_refusal_never_leaks_an_engine_name(self) -> None:
        with pytest.raises(LanguageNotSupportedError) as exc_info:
            self._tts().resolve("intelliai-tts", language="hi")
        assert "kokoro" not in exc_info.value.message.lower()


class TestRouteComposition:
    """Misconfiguration aborts startup, never surfaces at request time."""

    def test_route_for_unknown_model_cannot_compose(self) -> None:
        with pytest.raises(ValueError, match="unknown public model"):
            Registry(
                artifacts=[artifact()],
                models=[model()],
                routes=[route(public_model_id="intelliai-ocr")],
            )

    def test_route_to_unknown_artifact_cannot_compose(self) -> None:
        with pytest.raises(ValueError, match="unknown artifact"):
            Registry(artifacts=[artifact()], models=[model()], routes=[route(artifact_id="ghost")])

    def test_route_to_wrong_capability_cannot_compose(self) -> None:
        synth = artifact(id="synth", capability=Capability.SPEECH_SYNTHESIS)
        with pytest.raises(ValueError, match="different capability"):
            Registry(
                artifacts=[artifact(), synth],
                models=[model()],
                routes=[route(artifact_id="synth")],
            )

    def test_route_to_non_commercial_artifact_cannot_compose(self) -> None:
        research = artifact(id="research-only", license=NON_COMMERCIAL)
        with pytest.raises(ValueError, match="commercial-use license"):
            Registry(
                artifacts=[artifact(), research],
                models=[model()],
                routes=[route(artifact_id="research-only")],
            )

    def test_a_non_commercial_serving_path_cannot_compose(self) -> None:
        # The Hindi TTS gate was a GPL phonemizer, not a model: a
        # commercially clean artifact on a contaminated path still fails.
        with pytest.raises(ValueError, match="non-commercial serving path"):
            Registry(artifacts=[artifact()], models=[model()], routes=[route(license=GPL_PATH)])


class TestVoiceBinding:
    """The registry owns WHICH artifact serves a voice; the runtime owns
    HOW it renders it (M3's line, one level deeper)."""

    def _tts_parts(self) -> tuple[ArtifactRecord, PublicModelRecord]:
        return (
            artifact(id="kokoro-82m", capability=Capability.SPEECH_SYNTHESIS),
            model(
                id="intelliai-tts",
                capability=Capability.SPEECH_SYNTHESIS,
                service="tts-runtime",
                artifact_id="kokoro-82m",
            ),
        )

    def test_an_unbound_voice_rides_its_language_route(self) -> None:
        tts_artifact, tts_model = self._tts_parts()
        registry = Registry(
            artifacts=[tts_artifact],
            models=[tts_model],
            voices=[voice(model="intelliai-tts")],
        )
        assert registry.list_voices("intelliai-tts")[0].artifact_id is None

    def test_a_bound_voice_must_match_its_languages_route(self) -> None:
        tts_artifact, tts_model = self._tts_parts()
        other = artifact(id="other-tts", capability=Capability.SPEECH_SYNTHESIS)
        with pytest.raises(ValueError, match="must serve every language the voice claims"):
            Registry(
                artifacts=[tts_artifact, other],
                models=[tts_model],
                voices=[voice(model="intelliai-tts", artifact_id="other-tts")],
                routes=[
                    ServingRoute(
                        public_model_id="intelliai-tts",
                        selector=RouteSelector(language="en"),
                        status=LanguageStatus.AVAILABLE,
                        artifact_id="kokoro-82m",
                        license=MIT,
                    )
                ],
            )

    def test_a_voice_for_a_refused_language_cannot_compose(self) -> None:
        tts_artifact, tts_model = self._tts_parts()
        with pytest.raises(ValueError, match="does not serve"):
            Registry(
                artifacts=[tts_artifact],
                models=[tts_model],
                voices=[voice(model="intelliai-tts", languages=("hi",))],
                routes=[
                    ServingRoute(
                        public_model_id="intelliai-tts",
                        selector=RouteSelector(language="hi"),
                        status=LanguageStatus.UNAVAILABLE,
                    )
                ],
            )

    def test_a_voice_binding_an_unknown_artifact_cannot_compose(self) -> None:
        tts_artifact, tts_model = self._tts_parts()
        with pytest.raises(ValueError, match="binds unknown artifact"):
            Registry(
                artifacts=[tts_artifact],
                models=[tts_model],
                voices=[voice(model="intelliai-tts", artifact_id="ghost")],
            )

    def test_a_multilingual_voice_composes_when_every_language_agrees(self) -> None:
        tts_artifact, tts_model = self._tts_parts()
        registry = Registry(
            artifacts=[tts_artifact],
            models=[tts_model],
            voices=[voice(model="intelliai-tts", languages=("en", "hi"), artifact_id="kokoro-82m")],
            routes=[
                ServingRoute(
                    public_model_id="intelliai-tts",
                    selector=RouteSelector(language=lang),
                    status=LanguageStatus.AVAILABLE,
                    artifact_id="kokoro-82m",
                    license=MIT,
                )
                for lang in ("en", "hi")
            ],
        )
        assert registry.resolve("intelliai-tts", language="hi").artifact.id == "kokoro-82m"


class TestCapabilityAgnostic:
    """Nothing is hardwired to English, Hindi, or Arabic: invented
    languages route exactly as policy languages do."""

    def test_invented_languages_ladder_identically(self) -> None:
        future = artifact(id="future-engine")
        registry = Registry(
            artifacts=[artifact(), future],
            models=[model()],
            routes=[
                route(selector=RouteSelector(language="xx"), artifact_id="future-engine"),
                route(
                    selector=RouteSelector(language="zz"),
                    status=LanguageStatus.SUPPORTED,
                    evidence=EVIDENCE,
                ),
                ServingRoute(
                    public_model_id="intelliai-stt",
                    selector=RouteSelector(language="qq"),
                    status=LanguageStatus.UNAVAILABLE,
                ),
            ],
        )
        assert registry.resolve("intelliai-stt", language="xx-YY").artifact.id == "future-engine"
        assert registry.language_status("intelliai-stt", "zz") is LanguageStatus.SUPPORTED
        assert registry.served_languages("intelliai-stt") == ("xx", "zz")
        with pytest.raises(LanguageNotSupportedError):
            registry.resolve("intelliai-stt", language="qq")


class TestBehaviorFrozen:
    """Step 1 adds representation, not behavior: every path the gateway
    uses today answers exactly as it did at v0.5.0."""

    def test_undeclared_resolution_is_unchanged_for_both_capabilities(self) -> None:
        registry = default_registry()
        assert registry.resolve("intelliai-stt").artifact.id == "whisper-small"
        assert registry.resolve("intelliai-tts").artifact.id == "kokoro-82m"

    def test_deployment_defaults_to_the_service_name(self) -> None:
        # Today's topology is the degenerate case of ADR-0026: one
        # deployment per capability.
        for model_id, service in (
            ("intelliai-stt", "stt-runtime"),
            ("intelliai-tts", "tts-runtime"),
        ):
            assert default_registry().resolve(model_id).deployment == service

    def test_the_policy_language_routes_serve_the_approved_artifacts(self) -> None:
        # Originally the routes described what was already happening
        # (everything on the incumbent). Since the M26 founder decision,
        # Hindi is the first language served by a PROMOTED specialist;
        # English and Arabic stay on the incumbent unchanged.
        registry = default_registry()
        assert registry.resolve("intelliai-stt", language="hi").artifact.id == (
            "qwen3-asr-0.6b-hi-ft-e3"
        )
        for language in ("en", "ar"):
            assert registry.resolve("intelliai-stt", language=language).artifact.id == (
                "whisper-small"
            )
        assert registry.resolve("intelliai-tts", language="en").artifact.id == "kokoro-82m"


class TestDefaultLadder:
    """The Core Speech Language Policy ladder as ruled in F-M5-2."""

    def test_stt_ladder(self) -> None:
        registry = default_registry()
        assert registry.language_status("intelliai-stt", "en") is LanguageStatus.SUPPORTED
        assert registry.language_status("intelliai-stt", "hi") is LanguageStatus.AVAILABLE
        assert registry.language_status("intelliai-stt", "ar") is LanguageStatus.AVAILABLE

    def test_tts_ladder(self) -> None:
        registry = default_registry()
        assert registry.language_status("intelliai-tts", "en") is LanguageStatus.SUPPORTED
        assert registry.language_status("intelliai-tts", "hi") is LanguageStatus.UNAVAILABLE
        assert registry.language_status("intelliai-tts", "ar") is LanguageStatus.UNAVAILABLE

    def test_every_promise_cites_its_evidence(self) -> None:
        registry = default_registry()
        for model_id in ("intelliai-stt", "intelliai-tts"):
            for serving_route in registry.list_languages(model_id):
                if serving_route.status is LanguageStatus.SUPPORTED:
                    evidence = serving_route.evidence
                    assert evidence is not None
                    assert evidence.corpus and evidence.quality_baseline
                    assert evidence.production_benchmark and evidence.approval

    def test_every_served_route_has_a_commercial_serving_path_verdict(self) -> None:
        registry = default_registry()
        for model_id in ("intelliai-stt", "intelliai-tts"):
            for serving_route in registry.list_languages(model_id):
                if serving_route.status is LanguageStatus.UNAVAILABLE:
                    assert serving_route.license is None
                    continue
                verdict = serving_route.license
                assert verdict is not None
                assert verdict.commercial_use is True
                assert verdict.covers, "a route verdict must say what of the path it covers"

    def test_language_status_for_an_unknown_model_is_not_found(self) -> None:
        with pytest.raises(ModelNotFoundError):
            default_registry().language_status("gpt-4o", "en")

    def test_no_language_route_is_staged_below_production(self) -> None:
        registry = default_registry()
        for model_id in ("intelliai-stt", "intelliai-tts"):
            for serving_route in registry.list_languages(model_id):
                assert serving_route.stage is RouteStage.PRODUCTION
