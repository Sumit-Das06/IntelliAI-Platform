"""Operational CLI for the IntelliAI platform.

Charter: entrypoint only — argument parsing, session lifecycle (including
the commit), and human-readable output. All business logic lives in
services; this module may never import repositories or models directly.

Usage (via Makefile):
    make bootstrap-org org="Acme" email="you@example.com" name="You"
"""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from intelliai_api.analytics import (
    POLICY_LANGUAGES,
    FailureRate,
    LadderCoverage,
    LanguageReport,
    ReconciliationReport,
    UsageSpike,
    failure_rates,
    language_report,
    reconcile,
    reversal_activity,
    usage_spikes,
)
from intelliai_api.core.config import get_settings
from intelliai_api.core.errors import IntelliAIError
from intelliai_api.core.logging import configure_logging
from intelliai_api.core.time import utc_now
from intelliai_api.db.engine import create_engine, create_session_factory
from intelliai_api.entitlements import BillingPeriod, period_for
from intelliai_api.registry import default_registry
from intelliai_api.registry.manifest import serving_manifest
from intelliai_api.services.identity import BootstrapResult, IdentityService


def _print_bootstrap_result(result: BootstrapResult) -> None:
    print()
    print("=" * 64)
    print("Organization bootstrapped.")
    print("-" * 64)
    print(f"  organization : {result.organization.name}  ({result.organization.public_id})")
    print(f"  owner        : {result.owner.email}  ({result.owner.public_id})")
    print(f"  api key      : {result.api_key.name}  ({result.api_key.public_id})")
    print("-" * 64)
    print("  YOUR API KEY - shown once, never recoverable. Store it now:")
    print()
    print(f"      {result.generated.secret}")
    print()
    print("=" * 64)


async def _bootstrap_org(organization: str, email: str, name: str) -> None:
    settings = get_settings()
    configure_logging(settings)
    engine = create_engine(settings)
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            service = IdentityService(session, pepper=settings.auth.key_pepper.get_secret_value())
            result = await service.bootstrap_organization(
                organization_name=organization,
                owner_email=email,
                owner_name=name,
            )
            # The CLI owns the commit: the service defined the atomic scope,
            # the entrypoint pulls the trigger (same split as the request scope).
            await session.commit()
        _print_bootstrap_result(result)
    finally:
        await engine.dispose()


async def _commercial_report(month: str | None) -> int:
    """Reconcile the commercial plane and report what it found.

    The exit code is the point: this is meant to run on a schedule, and a
    reconciliation whose failure nobody notices is the silent revenue
    loss §6.1 exists to forbid.
    """
    settings = get_settings()
    configure_logging(settings)
    period = _period_from(month)
    engine = create_engine(settings)
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            fallback = (
                Path(settings.metering.fallback_path) if settings.metering.fallback_path else None
            )
            report = await reconcile(session, period, fallback_path=fallback)
            spikes = await usage_spikes(session, now=period.end)
            failures = await failure_rates(session, since=period.start, until=period.end)
            reversals = await reversal_activity(session, since=period.start, until=period.end)
            languages = await language_report(session, since=period.start, until=period.end)
    finally:
        await engine.dispose()

    contradictions = _print_commercial_report(report, spikes, failures, reversals, languages)
    # A ladder contradiction is a serving defect, and this command's
    # exit code is what a scheduler notices.
    return 0 if report.clean and not contradictions else 1


def _period_from(month: str | None) -> BillingPeriod:
    if month is None:
        return period_for(utc_now())
    try:
        year, month_number = (int(part) for part in month.split("-"))
    except ValueError as exc:
        raise SystemExit(f"--month must look like 2026-08, not {month!r}") from exc
    return period_for(datetime(year, month_number, 1, tzinfo=UTC))


def _print_commercial_report(
    report: ReconciliationReport,
    spikes: list[UsageSpike],
    failures: list[FailureRate],
    reversals: int,
    languages: LanguageReport,
) -> list[LadderCoverage]:
    print()
    print("=" * 72)
    print(f"COMMERCIAL PLANE REPORT — {report.period.label} (UTC)")
    print("=" * 72)
    print(f"  organizations with usage : {report.organizations}")
    print(f"  ledger events            : {report.events}")
    print(f"  rated from ledger        : {report.ledger_total}")
    print(f"  rated from rollups       : {report.rollup_total}")
    print(f"  reversals issued         : {reversals}")

    print("-" * 72)
    print("RECONCILIATION")
    if report.clean:
        print("  clean — gateway, ledger, rollups and rating agree")
    for finding in report.findings:
        print(f"  [{finding.severity}] {finding.check}: {finding.detail}")

    print("-" * 72)
    print("ANOMALIES")
    if not spikes and not failures:
        print("  none")
    for spike in spikes:
        print(
            f"  [warning] usage spike: org {spike.organization_id} used {spike.recent} "
            f"{spike.unit} vs a {spike.baseline} baseline ({spike.multiple:.1f}x)"
        )
    for failure in failures:
        print(
            f"  [warning] failure rate: org {failure.organization_id} "
            f"{failure.failure_share:.0%} non-billable "
            f"({failure.failed} failed / {failure.succeeded} served)"
        )

    print("-" * 72)
    print("LANGUAGE ADOPTION (Core Speech Language Policy)")
    adoption = languages.adoption()
    for language in POLICY_LANGUAGES:
        print(f"  {language} : {adoption.get(language, 0)} organization(s)")
    unserved = languages.unserved_demand()
    print(f"  outside the policy : {', '.join(unserved) if unserved else 'none'}")

    print("-" * 72)
    print("LADDER COVERAGE (what we promise, beside what we served)")
    contradictions: list[LadderCoverage] = []
    for row in languages.against_ladder(_shipped_ladder()):
        marker = "  !! " if row.is_contradiction else "     "
        print(
            f"{marker}{row.capability:<18} {row.language:<3} {row.status:<12} "
            f"{row.requests:>5} request(s)  {row.organizations:>3} org(s)"
        )
        if row.is_contradiction:
            contradictions.append(row)
    for row in contradictions:
        print(
            f"  [error] served {row.language!r} for {row.capability} while the ladder "
            f"says {row.status} — a serving defect, not a usage pattern"
        )
    print("=" * 72)
    return contradictions


def _shipped_ladder() -> dict[tuple[str, str], str]:
    """The rung the registry currently states for every (capability, language).

    Read from the registry rather than restated here: a report that
    carried its own copy of the ladder would eventually disagree with
    what the platform actually serves, and disagree silently.
    """
    registry = default_registry()
    return {
        (model.capability.value, route.selector.language): route.status.value
        for model in registry.list_models()
        for route in registry.list_languages(model.id)
        if route.selector.language is not None
    }


def _registry_manifest(out: Path) -> int:
    """Export resolved registry state — the evaluation plane's only view.

    Composition runs first (the catalog is validated on import), so a
    manifest can only be written from a registry that would actually
    serve. Deterministic by construction: same catalog, same bytes.
    """
    document = serving_manifest(default_registry())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    routes = sum(len(model["routes"]) for model in document["models"])
    print(f"resolved {len(document['models'])} public models, {routes} routes -> {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="intelliai", description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)

    bootstrap = subcommands.add_parser(
        "bootstrap-org", help="Create an organization with an owner and first API key"
    )
    bootstrap.add_argument("--org-name", required=True)
    bootstrap.add_argument("--owner-email", required=True)
    bootstrap.add_argument("--owner-name", required=True)

    report = subcommands.add_parser(
        "commercial-report",
        help="Reconcile the commercial plane; exits non-zero if anything disagrees",
    )
    report.add_argument("--month", help="billing period as YYYY-MM (default: current)")

    manifest = subcommands.add_parser(
        "registry-manifest",
        help="Export resolved registry state for readers outside the gateway",
    )
    manifest.add_argument("--out", type=Path, required=True, help="manifest JSON path")

    args = parser.parse_args(argv)

    try:
        if args.command == "registry-manifest":
            return _registry_manifest(args.out)
        if args.command == "commercial-report":
            return asyncio.run(_commercial_report(args.month))
        asyncio.run(_bootstrap_org(args.org_name, args.owner_email, args.owner_name))
    except IntelliAIError as exc:
        print(f"error [{exc.code}]: {exc.message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
