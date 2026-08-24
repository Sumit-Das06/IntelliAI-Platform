"""Reading usage against the ladder: promise beside traffic.

Two silences look identical in a usage report and mean opposite things.
A `supported` language with no traffic is a product problem. An
`unavailable` language *with* traffic is a serving defect — the gateway
refuses those before crossing a plane, so a row like that means the
refusal stopped working. Adoption numbers alone cannot tell them apart.
"""

from datetime import UTC, datetime
from decimal import Decimal

from intelliai_api.analytics import LadderCoverage, LanguageReport, LanguageUsage
from intelliai_api.registry import LanguageStatus, default_registry

SHIPPED_LADDER = {
    (model.capability.value, route.selector.language): route.status.value
    for model in default_registry().list_models()
    for route in default_registry().list_languages(model.id)
    if route.selector.language is not None
}


def usage(language: str | None, capability: str, requests: int = 1) -> LanguageUsage:
    return LanguageUsage(
        language=language,
        capability=capability,
        requests=requests,
        organizations=1,
        quantities={"audio_seconds": Decimal(1)},
    )


def report(*rows: LanguageUsage) -> LanguageReport:
    return LanguageReport(
        since=datetime(2026, 8, 1, tzinfo=UTC),
        until=datetime(2026, 9, 1, tzinfo=UTC),
        rows=rows,
    )


class TestLadderJoin:
    def test_every_shipped_rung_appears_even_with_no_traffic(self) -> None:
        rows = report().against_ladder(SHIPPED_LADDER)
        assert {(row.capability, row.language) for row in rows} == set(SHIPPED_LADDER)
        assert all(row.requests == 0 for row in rows)

    def test_traffic_lands_on_its_own_capability_and_language(self) -> None:
        rows = report(
            usage("en", "transcription", requests=4),
            usage("hi", "transcription", requests=2),
            usage("en", "speech_synthesis", requests=3),
        ).against_ladder(SHIPPED_LADDER)
        by_key = {(row.capability, row.language): row for row in rows}
        assert by_key[("transcription", "en")].requests == 4
        assert by_key[("transcription", "hi")].requests == 2
        assert by_key[("speech_synthesis", "en")].requests == 3
        # Synthesis Hindi is served but unused here: a ladder row with
        # no traffic, which `available` makes neither a defect nor a
        # broken promise.
        assert by_key[("speech_synthesis", "hi")].requests == 0

    def test_regional_tags_fold_into_their_base_subtag(self) -> None:
        rows = report(usage("hi-IN", "transcription", requests=5)).against_ladder(SHIPPED_LADDER)
        by_key = {(row.capability, row.language): row for row in rows}
        assert by_key[("transcription", "hi")].requests == 5


class TestSignals:
    def test_traffic_on_a_refused_language_is_a_contradiction(self) -> None:
        # Arabic synthesis is the platform's refused route since the
        # M42 promotion moved Hindi synthesis onto the ladder.
        rows = report(usage("ar", "speech_synthesis", requests=1)).against_ladder(SHIPPED_LADDER)
        flagged = [row for row in rows if row.is_contradiction]
        assert [(row.capability, row.language) for row in flagged] == [("speech_synthesis", "ar")]

    def test_a_promise_nobody_used_is_a_product_signal_not_a_defect(self) -> None:
        rows = report().against_ladder(SHIPPED_LADDER)
        unexercised = {(row.capability, row.language) for row in rows if row.is_unexercised_promise}
        assert unexercised == {("transcription", "en"), ("speech_synthesis", "en")}
        assert not [row for row in rows if row.is_contradiction]

    def test_an_available_language_with_no_traffic_is_neither(self) -> None:
        # `available` is honest either way: it promises nothing, so its
        # silence is not a broken promise and its traffic is not a defect.
        (row,) = [
            row
            for row in report().against_ladder(SHIPPED_LADDER)
            if (row.capability, row.language) == ("transcription", "ar")
        ]
        assert row.status == LanguageStatus.AVAILABLE.value
        assert row.is_contradiction is False
        assert row.is_unexercised_promise is False


class TestShippedLadder:
    def test_it_is_read_from_the_registry_not_restated(self) -> None:
        # A report carrying its own copy of the ladder would eventually
        # disagree with what the platform serves, and disagree silently.
        assert SHIPPED_LADDER[("transcription", "hi")] == "available"
        assert SHIPPED_LADDER[("speech_synthesis", "hi")] == "available"  # M42 promotion
        assert SHIPPED_LADDER[("speech_synthesis", "ar")] == "unavailable"
        assert SHIPPED_LADDER[("transcription", "en")] == "supported"

    def test_both_capabilities_are_covered(self) -> None:
        # "Language analytics complete for both capabilities" — synthesis
        # only started recording language in M5 step 3.
        capabilities = {capability for capability, _ in SHIPPED_LADDER}
        assert capabilities == {"transcription", "speech_synthesis"}


def test_coverage_rows_are_frozen_facts() -> None:
    row = LadderCoverage(
        capability="transcription", language="hi", status="available", requests=0, organizations=0
    )
    assert row.is_contradiction is False
