"""The registry is complete, dated, and honest about access."""

import pytest

from intelliai_datasets.sources import SOURCES, Access, CommercialVerdict, source, usable_now


class TestRegistry:
    def test_every_record_carries_a_dated_license_read(self) -> None:
        for record in SOURCES:
            assert record.license, record.name
            assert record.license_verified_on, record.name
            assert record.license_source_url.startswith("https://"), record.name

    def test_gated_and_blocked_records_explain_themselves(self) -> None:
        for record in SOURCES:
            if record.access is not Access.OPEN:
                assert record.access_detail, f"{record.name} must say what unblocks it"

    def test_only_open_commercial_sources_are_usable_now(self) -> None:
        usable = {r.name for r in SOURCES if usable_now(r)}
        # M22 added the in-repo negative sources: generated audio and
        # locally derived segments of already-approved clips are OPEN by
        # construction — no external gate exists to record.
        assert usable == {"fleurs", "negatives-synthetic", "negatives-indicvoices-derived"}

    def test_the_approved_primaries_are_registered_even_though_blocked(self) -> None:
        for name in ("indicvoices", "kathbath", "common-voice-hi", "lahaja"):
            record = source(name)
            assert record.commercial is CommercialVerdict.YES

    def test_unknown_source_is_refused_loudly(self) -> None:
        with pytest.raises(KeyError, match="registered"):
            source("does-not-exist")
