"""Derived reports: regenerable readings that decide nothing.

Each test holds one of the five structural guarantees, against real
committed evidence wherever one exists.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from intelliai_evaluation.reports import (
    STANDING_COST_FACTORS,
    CostFactor,
    PromotionPackage,
    comparability_findings,
    regression_markdown,
    summary_markdown,
    switching_markdown,
)
from intelliai_evaluation.results import EvalRun

RESULTS = Path("ml/evaluation/stt/results")
PH0_RECORD = RESULTS / "2026-08-06-intelliai-stt-en-whisper-small-int8-ph0.json"
PH0_REPLICATE = RESULTS / "2026-08-06-intelliai-stt-en-whisper-small-int8-ph0-replicate.json"
LEGACY_RECORD = RESULTS / "2026-08-05-intelliai-stt-en.json"
COMMITTED_SUMMARY = Path(
    "ml/evaluation/stt/benchmarks/2026-08-06-intelliai-stt-en-whisper-small-int8-ph0-summary.md"
)
REPORTS_SOURCE = Path("ml/evaluation/src/intelliai_evaluation/reports.py")


def load(path: Path) -> EvalRun:
    return EvalRun.model_validate_json(path.read_text(encoding="utf-8"))


def reshape(run: EvalRun, **metric_overrides: float) -> EvalRun:
    return run.model_copy(update={"metrics": {**run.metrics, **metric_overrides}})


# ─────────────────────────────────────────────────────────────────────
# Byte-reproducibility
# ─────────────────────────────────────────────────────────────────────


class TestReportsAreByteReproducible:
    def test_the_same_record_renders_the_same_bytes(self) -> None:
        run = load(PH0_RECORD)
        first = summary_markdown(run, record_name=PH0_RECORD.name)
        second = summary_markdown(run, record_name=PH0_RECORD.name)
        assert first == second

    def test_the_committed_summary_is_exactly_a_regeneration(self) -> None:
        # The drift guard, in the manifest-drift pattern: the committed
        # derived document must equal a fresh regeneration, so a hand
        # edit — the thing a derived artifact must never receive — fails
        # CI rather than surviving review.
        regenerated = summary_markdown(load(PH0_RECORD), record_name=PH0_RECORD.name)
        assert COMMITTED_SUMMARY.read_text(encoding="utf-8") == regenerated

    def test_the_generator_reads_no_clock_and_no_environment(self) -> None:
        # Byte-reproducible forever means: a report's only dates are its
        # records'. The module must not import time sources or touch the
        # filesystem/environment.
        tree = ast.parse(REPORTS_SOURCE.read_text(encoding="utf-8"))
        roots = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0
        }
        assert not roots & {"time", "datetime", "os", "pathlib", "random", "httpx"}

    def test_comparisons_are_reproducible_too(self) -> None:
        a, b = load(PH0_RECORD), load(PH0_REPLICATE)
        names = (PH0_RECORD.name, PH0_REPLICATE.name)
        one = regression_markdown(a, b, baseline_name=names[0], current_name=names[1])
        two = regression_markdown(a, b, baseline_name=names[0], current_name=names[1])
        assert one == two


# ─────────────────────────────────────────────────────────────────────
# No decisions, no winners, no scores
# ─────────────────────────────────────────────────────────────────────


class TestReportsDecideNothing:
    def test_the_switching_report_names_no_winner_and_no_verdict(self) -> None:
        rendered = switching_markdown(
            load(PH0_RECORD),
            load(PH0_REPLICATE),
            incumbent_name=PH0_RECORD.name,
            challenger_name=PH0_REPLICATE.name,
        )
        lowered = rendered.lower()
        for decision_word in ("winner", "passed", "refused", "recommend", "adopt", "verdict:"):
            assert decision_word not in lowered
        assert "decides nothing" in lowered

    def test_cost_factors_are_structurally_unpriceable(self) -> None:
        # No magnitude, no weight, no total: the report cannot sum its
        # way to an outcome. Pricing a switch is the deciding human's
        # act, in the promotion diff.
        assert set(CostFactor.__dataclass_fields__) == {"description", "owner"}
        for factor in STANDING_COST_FACTORS:
            assert not any(
                isinstance(getattr(factor, name), (int, float))
                for name in CostFactor.__dataclass_fields__
            )

    def test_the_promotion_package_cannot_carry_the_recommendation(self) -> None:
        # The evidence bundle and the argument never travel as one
        # object. There is no field to put the recommendation in.
        fields = set(PromotionPackage.__dataclass_fields__)
        assert "recommendation" not in fields
        assert "verdict" not in fields
        assert "score" not in fields
        assert "winner" not in fields

    def test_the_package_serialises_without_inventing_one(self) -> None:
        package = PromotionPackage(
            subject="intelliai-stt/en",
            records=(PH0_RECORD.name,),
            summaries=(COMMITTED_SUMMARY.name,),
        )
        assert '"recommendation"' not in package.to_json()

    def test_no_report_rolls_up_across_languages(self) -> None:
        # One record, one language, one report; the summary renders the
        # slug's single language and there is no API that takes a set of
        # languages to aggregate.
        rendered = summary_markdown(load(PH0_RECORD), record_name=PH0_RECORD.name)
        assert "| Language | `en` |" in rendered
        import intelliai_evaluation.reports as reports_module

        assert not [name for name in dir(reports_module) if "overall" in name.lower()]


# ─────────────────────────────────────────────────────────────────────
# Direction is computed; blocked stays blocked
# ─────────────────────────────────────────────────────────────────────


class TestDirectionComesOnlyFromTheRegistry:
    def test_a_lower_is_better_increase_is_a_regression(self) -> None:
        baseline = load(PH0_RECORD)
        worsened = reshape(load(PH0_REPLICATE), wer_unicode=0.5)
        rendered = regression_markdown(
            baseline, worsened, baseline_name="a.json", current_name="b.json"
        )
        assert "| `wer_unicode` | 0.0000 | 0.5000 | +0.5000 | regressed |" in rendered

    def test_a_lower_is_better_decrease_is_an_improvement(self) -> None:
        baseline = reshape(load(PH0_RECORD), wer_unicode=0.5)
        improved = load(PH0_REPLICATE)
        rendered = regression_markdown(
            baseline, improved, baseline_name="a.json", current_name="b.json"
        )
        assert "| `wer_unicode` | 0.5000 | 0.0000 | -0.5000 | improved |" in rendered

    def test_correctness_deltas_read_real_and_wall_clock_reads_no_band(self) -> None:
        # §6.3: there is no "any non-zero delta is real" rule — our own
        # kokoro replicate pair refutes it. Correctness metrics are
        # deterministic computations over fixed texts; performance has no
        # replicate band yet and says so.
        baseline = load(PH0_RECORD)
        current = reshape(load(PH0_REPLICATE), wer_unicode=0.1)
        rendered = regression_markdown(
            baseline, current, baseline_name="a.json", current_name="b.json"
        )
        assert "| regressed | real |" in rendered
        assert "no_band_established" in rendered  # recognition_rtf moved between runs


class TestBlockedComparisonsStayBlocked:
    def test_a_pre_methodology_record_cannot_prove_its_ruler(self) -> None:
        # The PH0 F-3 era boundary, enforced: the M5-era record carries no
        # execution context, so nothing can prove which ruler produced it.
        findings = comparability_findings(load(LEGACY_RECORD), load(PH0_RECORD))
        assert "normalization_profile_unrecorded" in {finding.code for finding in findings}

    def test_a_blocked_regression_report_shows_no_deltas(self) -> None:
        rendered = regression_markdown(
            load(LEGACY_RECORD),
            load(PH0_RECORD),
            baseline_name=LEGACY_RECORD.name,
            current_name=PH0_RECORD.name,
        )
        assert "BLOCKED" in rendered
        assert "No delta below this line exists" in rendered
        assert "| `wer_unicode` |" not in rendered

    def test_a_blocked_switching_report_makes_the_block_the_headline(self) -> None:
        rendered = switching_markdown(
            load(LEGACY_RECORD),
            load(PH0_RECORD),
            incumbent_name=LEGACY_RECORD.name,
            challenger_name=PH0_RECORD.name,
        )
        assert "NOT COMPARABLE" in rendered
        assert "Per-metric evidence" not in rendered

    def test_different_corpus_versions_block(self) -> None:
        run = load(PH0_RECORD)
        assert run.identity is not None
        other = run.model_copy(
            update={"identity": run.identity.model_copy(update={"dataset_version": 99})}
        )
        findings = comparability_findings(run, other)
        assert "different_corpus_version" in {finding.code for finding in findings}

    def test_comparable_records_produce_no_findings(self) -> None:
        assert comparability_findings(load(PH0_RECORD), load(PH0_REPLICATE)) == ()


# ─────────────────────────────────────────────────────────────────────
# Summaries render evidence facts faithfully
# ─────────────────────────────────────────────────────────────────────


class TestSummaryFidelity:
    def test_it_refuses_a_record_without_an_identity(self) -> None:
        run = load(PH0_RECORD).model_copy(update={"identity": None})
        with pytest.raises(ValueError, match="cannot be summarised"):
            summary_markdown(run, record_name="x.json")

    def test_validity_none_renders_as_not_computed_never_as_a_state(self) -> None:
        rendered = summary_markdown(load(PH0_RECORD), record_name=PH0_RECORD.name)
        assert "| Validity | not computed |" in rendered

    def test_an_unnamed_run_is_visibly_not_a_baseline(self) -> None:
        rendered = summary_markdown(load(PH0_RECORD), record_name=PH0_RECORD.name)
        assert "not a named baseline" in rendered

    def test_determinations_render_with_their_provenance(self) -> None:
        rendered = summary_markdown(load(PH0_RECORD), record_name=PH0_RECORD.name)
        assert "| `hardware_class_unruled` | not_measured | harness | fact |" in rendered

    def test_every_metric_line_carries_its_computed_direction(self) -> None:
        rendered = summary_markdown(load(PH0_RECORD), record_name=PH0_RECORD.name)
        assert "| `wer_unicode` | 0.0000 | lower |" in rendered
        assert "| `recognition_rtf` | 0.1310 | lower |" in rendered
