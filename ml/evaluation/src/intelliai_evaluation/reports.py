"""Derived reports — readings of evidence that decide nothing.

Records are evidence: immutable, self-contained, written once by the
instrument. Everything here is a *reading* of them — regenerable, byte-
reproducible, and quotable for convenience only. Citations name records;
a report is re-derived for truth, never cited as a source.

**Five structural guarantees**, held by shape rather than by review:

1. No field anywhere holds a shipping decision, a verdict, or a winner.
2. No roll-up exists across languages — there is nowhere to put one.
3. :class:`CostFactor` has no magnitude, no weight, and no total, so the
   switching report structurally cannot compute an outcome.
4. The promotion package manifest has no field for a recommendation
   document — the evidence bundle and the argument never travel as one.
5. Direction of change is computed from :class:`MetricSpec.direction`,
   never authored — a report cannot accidentally call an improvement a
   regression.

**Byte-reproducibility is a design constraint, not a nicety.** The same
records in produce the same bytes out, forever: no wall-clock, no
environment reads, no randomness. A report's only dates are its records'.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Final

from intelliai_evaluation.evidence import Determination
from intelliai_evaluation.metrics import METRICS, MetricDirection, MetricLayer
from intelliai_evaluation.results import EvalRun

# ─────────────────────────────────────────────────────────────────────
# Benchmark summary — one record, rendered
# ─────────────────────────────────────────────────────────────────────


def summary_markdown(run: EvalRun, *, record_name: str) -> str:
    """One record's human-readable face. Regenerated, never edited.

    ``record_name`` is the committed record's own name (its identity as a
    citation), passed in rather than derived from a filesystem path — a
    report must not know where files live.
    """
    identity = run.identity
    if identity is None:
        msg = (
            "a record without an evaluation identity cannot be summarised: "
            "it does not say what it measured"
        )
        raise ValueError(msg)

    lines: list[str] = []
    lines.append(f"# Benchmark summary — {identity.slug}")
    lines.append("")
    lines.append(
        "> **Derived report.** Regenerated from "
        f"[`{record_name}`]({record_name}); never edited by hand and never "
        "citable as evidence — citations name the record."
    )
    lines.append("")
    lines.append("## Identity")
    lines.append("")
    lines.append("| | |")
    lines.append("|---|---|")
    lines.append(f"| Subject | `{identity.public_model}` |")
    lines.append(f"| Language | `{identity.language}` |")
    lines.append(
        f"| Artifact | `{identity.artifact}` v{identity.artifact_version} ({identity.build}) |"
    )
    lines.append(f"| Deployment | `{identity.deployment}` |")
    lines.append(f"| Corpus | `{identity.dataset}@v{identity.dataset_version}` |")
    lines.append(f"| Run at | {run.run_at.isoformat()} |")
    if run.session_id:
        lines.append(f"| Session | `{run.session_id}` |")
    baseline = identity.benchmark if identity.benchmark else "— (not a named baseline)"
    lines.append(f"| Named baseline | {baseline} |")
    validity = run.validity.value if run.validity else "not computed"
    lines.append(f"| Validity | {validity} |")
    lines.append("")

    if run.execution is not None:
        execution = run.execution
        lines.append("## Execution")
        lines.append("")
        lines.append("| | |")
        lines.append("|---|---|")
        lines.append(f"| Route | `{execution.route.value}` |")
        lines.append(f"| Ruler | `{execution.normalization}` |")
        lines.append(
            f"| Language mode | `{execution.language_mode.value}` "
            f"(declared `{execution.declared_language}`) |"
        )
        lines.append(f"| Emitted unit | `{execution.emitted_unit.value}` |")
        lines.append(f"| VAD owner | `{execution.vad_owner.value}` |")
        lines.append(f"| Timestamp source | `{execution.timestamp_source.value}` |")
        decode = ", ".join(f"{k}={v}" for k, v in sorted(execution.decode_params.items()))
        lines.append(f"| Decode configuration | {decode} |")
        environment = execution.environment
        if environment is not None:
            machine = environment.cpu_model or "unreported"
            era = environment.hardware_class or "unruled"
            lines.append(f"| Machine | {machine} (class: {era}) |")
        lines.append("")

    if run.load_ms is not None or run.warmup_ms is not None:
        lines.append("## Startup lifecycle")
        lines.append("")
        lines.append(f"- model load: {run.load_ms} ms · warm-up: {run.warmup_ms} ms")
        lines.append("")

    if run.coverage is not None:
        coverage = run.coverage
        lines.append("## Slice coverage")
        lines.append("")
        lines.append(
            f"- {coverage.clips} clip(s): {coverage.natural_speech_clips} natural speech, "
            f"{coverage.probe_clips} probe(s); {coverage.reference_words} reference word(s)"
        )
        claim = "yes" if coverage.is_quality_claim else "no — not citable as a quality claim"
        lines.append(f"- quality claim: {claim}")
        lines.append("")

    if run.metrics:
        lines.append("## Metrics")
        lines.append("")
        lines.append("| Metric | Value | Better |")
        lines.append("|---|---|---|")
        for name in sorted(run.metrics):
            spec = METRICS.require(name)
            better = "lower" if spec.direction is MetricDirection.LOWER_IS_BETTER else "higher"
            lines.append(f"| `{name}` | {run.metrics[name]:.4f} | {better} |")
        lines.append("")

    failures = [clip for clip in run.clips if clip.failure]
    if failures:
        lines.append("## Failures (evidence, not omissions)")
        lines.append("")
        for clip in failures:
            lines.append(f"- `{clip.clip_id}`: {clip.failure}")
        lines.append("")

    if run.determinations:
        lines.append("## Determinations — absence recorded as evidence")
        lines.append("")
        lines.append("| Code | State | By | Basis |")
        lines.append("|---|---|---|---|")
        for determination in run.determinations:
            lines.append(
                f"| `{determination.code}` | {determination.state.value} "
                f"| {determination.authored_by.value} | {determination.basis.value} |"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# ─────────────────────────────────────────────────────────────────────
# Comparability — checked first, and a block is a headline
# ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ComparabilityFinding:
    code: str
    detail: str


def comparability_findings(left: EvalRun, right: EvalRun) -> tuple[ComparabilityFinding, ...]:
    """Everything that must match before a delta means anything.

    Stricter than the promotion layer's check, deliberately: since B4b a
    record can state its normalization profile, so two records that
    cannot BOTH prove the same ruler are not comparable — which blocks
    every pre-methodology record until the incumbent is re-baselined
    under the new instrument (the PH0 F-3 era boundary, enforced rather
    than remembered).
    """
    findings: list[ComparabilityFinding] = []
    a, b = left.identity, right.identity
    if a is None or b is None:
        return (
            ComparabilityFinding(
                "identity_missing",
                "a run without an evaluation identity cannot be compared",
            ),
        )
    if a.public_model != b.public_model:
        findings.append(
            ComparabilityFinding("different_subject", f"{a.public_model} vs {b.public_model}")
        )
    if a.language != b.language:
        findings.append(ComparabilityFinding("different_language", f"{a.language} vs {b.language}"))
    if (a.dataset, a.dataset_version) != (b.dataset, b.dataset_version):
        findings.append(
            ComparabilityFinding(
                "different_corpus_version",
                f"{a.dataset}@v{a.dataset_version} vs {b.dataset}@v{b.dataset_version}",
            )
        )
    if a.judge != b.judge:
        findings.append(
            ComparabilityFinding("different_judge", "a judge upgrade re-baselines every incumbent")
        )
    left_ruler = left.execution.normalization if left.execution else None
    right_ruler = right.execution.normalization if right.execution else None
    if left_ruler is None or right_ruler is None:
        findings.append(
            ComparabilityFinding(
                "normalization_profile_unrecorded",
                "a pre-methodology record cannot prove which ruler produced it; "
                "re-baseline under the current instrument before comparing",
            )
        )
    elif left_ruler != right_ruler:
        findings.append(
            ComparabilityFinding(
                "different_normalization_profile", f"{left_ruler} vs {right_ruler}"
            )
        )
    return tuple(findings)


# ─────────────────────────────────────────────────────────────────────
# Regression report — what moved, and whether that is distinguishable
# from noise. Never whether it is acceptable.
# ─────────────────────────────────────────────────────────────────────

#: §6.3 readings. `real` is claimed only for correctness-layer metrics —
#: deterministic computations over fixed texts. Performance metrics get
#: `no_band_established` until same-identity replicates establish a noise
#: band; there is deliberately no "any non-zero delta is real" rule,
#: which our own kokoro replicate pair refutes.
_READING_REAL: Final = "real"
_READING_NO_BAND: Final = "no_band_established"


def _reading(name: str) -> str:
    spec = METRICS.require(name)
    return _READING_REAL if spec.layer is MetricLayer.CORRECTNESS else _READING_NO_BAND


def regression_markdown(
    baseline: EvalRun,
    current: EvalRun,
    *,
    baseline_name: str,
    current_name: str,
) -> str:
    """Two records of one lineage, differenced — or blocked, loudly.

    A blocked comparison is REPORTED as blocked with the findings named,
    never silently skipped: "we cannot tell" and "nothing moved" are
    different answers, and collapsing them is how regressions ship.
    """
    lines: list[str] = []
    lines.append("# Regression report")
    lines.append("")
    lines.append(f"- baseline: [`{baseline_name}`]({baseline_name})")
    lines.append(f"- current:  [`{current_name}`]({current_name})")
    lines.append("")

    findings = comparability_findings(baseline, current)
    if findings:
        lines.append("## BLOCKED — these records are not comparable")
        lines.append("")
        lines.append("No delta below this line exists. The blocking findings:")
        lines.append("")
        for finding in findings:
            lines.append(f"- `{finding.code}`: {finding.detail}")
        return "\n".join(lines).rstrip() + "\n"

    shared = sorted(set(baseline.metrics) & set(current.metrics))
    only_baseline = sorted(set(baseline.metrics) - set(current.metrics))
    only_current = sorted(set(current.metrics) - set(baseline.metrics))

    lines.append("## Deltas")
    lines.append("")
    lines.append(
        "Direction of change is computed from the metric registry, never "
        "authored. A `no_band_established` reading is not noise — it is the "
        "absence of a replicate band, and stays that way until one exists."
    )
    lines.append("")
    lines.append("| Metric | Baseline | Current | Delta | Direction | Reading |")
    lines.append("|---|---|---|---|---|---|")
    for name in shared:
        spec = METRICS.require(name)
        before, after = baseline.metrics[name], current.metrics[name]
        delta = after - before
        if delta == 0:
            direction = "unchanged"
        else:
            lower_is_better = spec.direction is MetricDirection.LOWER_IS_BETTER
            improved = (delta < 0) if lower_is_better else (delta > 0)
            direction = "improved" if improved else "regressed"
        lines.append(
            f"| `{name}` | {before:.4f} | {after:.4f} | {delta:+.4f} "
            f"| {direction} | {_reading(name)} |"
        )
    lines.append("")
    if only_baseline or only_current:
        lines.append("## Coverage changes")
        lines.append("")
        for name in only_baseline:
            lines.append(f"- `{name}`: present in baseline only — not differenced")
        for name in only_current:
            lines.append(f"- `{name}`: present in current only — not differenced")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# ─────────────────────────────────────────────────────────────────────
# Switching report — the evidence bundle for a decision made elsewhere
# ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CostFactor:
    """One cost of switching, named and owned — and deliberately unpriced.

    No magnitude, no weight, no total: the report must be structurally
    unable to sum its way to a verdict. Pricing a switch is the deciding
    human's act, in the promotion diff, in writing.
    """

    description: str
    owner: str


#: The standing switching costs (record spec §4). Data, not policy:
#: listing a cost does not price it.
STANDING_COST_FACTORS: Final[tuple[CostFactor, ...]] = (
    CostFactor("re-tuning capital invested in the incumbent is reset", "engineering"),
    CostFactor("every language slice must be re-evaluated under the challenger", "engineering"),
    CostFactor("serving-stack change and its operational unknowns", "engineering"),
    CostFactor("recipe knowledge (decode settings, failure modes) resets", "engineering"),
    CostFactor("judge coupling: a synthesis judge swap re-baselines TTS evidence", "research"),
)


def switching_markdown(
    incumbent: EvalRun,
    challenger: EvalRun,
    *,
    incumbent_name: str,
    challenger_name: str,
    cost_factors: tuple[CostFactor, ...] = STANDING_COST_FACTORS,
) -> str:
    """Challenger beside incumbent: findings, deltas, costs. No winner.

    If the records are not comparable, that fact IS the headline, and no
    delta is shown at all.
    """
    lines: list[str] = []
    lines.append("# Switching report")
    lines.append("")
    lines.append(f"- incumbent:  [`{incumbent_name}`]({incumbent_name})")
    lines.append(f"- challenger: [`{challenger_name}`]({challenger_name})")
    lines.append("")
    lines.append(
        "> **This report decides nothing.** It arranges evidence for the "
        "switching decision, which is made by a human, in a promotion diff, "
        "against costs that are named below and priced nowhere in this "
        "document."
    )
    lines.append("")

    findings = comparability_findings(incumbent, challenger)
    if findings:
        lines.append("## NOT COMPARABLE — the headline, not a footnote")
        lines.append("")
        for finding in findings:
            lines.append(f"- `{finding.code}`: {finding.detail}")
        lines.append("")
    else:
        lines.append("## Per-metric evidence")
        lines.append("")
        lines.append("| Metric | Incumbent | Challenger | Delta | Direction | Reading |")
        lines.append("|---|---|---|---|---|---|")
        for name in sorted(set(incumbent.metrics) & set(challenger.metrics)):
            spec = METRICS.require(name)
            a, b = incumbent.metrics[name], challenger.metrics[name]
            delta = b - a
            if delta == 0:
                direction = "unchanged"
            else:
                lower_is_better = spec.direction is MetricDirection.LOWER_IS_BETTER
                improved = (delta < 0) if lower_is_better else (delta > 0)
                direction = "challenger better" if improved else "challenger worse"
            lines.append(
                f"| `{name}` | {a:.4f} | {b:.4f} | {delta:+.4f} | {direction} | {_reading(name)} |"
            )
        lines.append("")

    lines.append("## Switching costs — named and owned, never priced")
    lines.append("")
    lines.append("| Cost | Owner |")
    lines.append("|---|---|")
    for factor in cost_factors:
        lines.append(f"| {factor.description} | {factor.owner} |")
    lines.append("")
    lines.append(
        "The standing law: a challenger must beat the tuned incumbent by a "
        "margin exceeding the full switching cost. This document cannot "
        "compute that margin, by construction."
    )
    return "\n".join(lines).rstrip() + "\n"


# ─────────────────────────────────────────────────────────────────────
# Promotion package manifest — the bundle, without the argument
# ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PromotionPackage:
    """Everything a promotion review reads, listed by name.

    A dossier of evidence, not a recommendation — and structurally unable
    to become one: there is **no field for the recommendation document**,
    so the evidence bundle and the argument never travel as one object.
    """

    subject: str  # e.g. "intelliai-stt/en" — the promise and slice at issue
    records: tuple[str, ...]  # evidence record names, all languages
    summaries: tuple[str, ...] = ()
    regression_report: str | None = None
    switching_report: str | None = None
    licence_verdict: str | None = None  # the dated Gate-1-format re-verification
    deployment_evidence: str | None = None
    open_questions: tuple[str, ...] = ()
    determinations: tuple[Determination, ...] = ()

    def to_json(self) -> str:
        document = {
            "subject": self.subject,
            "records": list(self.records),
            "summaries": list(self.summaries),
            "regression_report": self.regression_report,
            "switching_report": self.switching_report,
            "licence_verdict": self.licence_verdict,
            "deployment_evidence": self.deployment_evidence,
            "open_questions": list(self.open_questions),
            "determinations": [
                json.loads(determination.model_dump_json()) for determination in self.determinations
            ],
        }
        return json.dumps(document, indent=2, ensure_ascii=False) + "\n"
