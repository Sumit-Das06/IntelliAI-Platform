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
from intelliai_api.services.erasure import ErasureReport, ErasureService
from intelliai_api.services.identity import (
    DEFAULT_TENANT_ORIGIN,
    TENANT_ORIGINS,
    BootstrapResult,
    IdentityService,
    tenant_origin,
)


def _print_bootstrap_result(result: BootstrapResult) -> None:
    origin = result.organization.usage_origin
    print()
    print("=" * 64)
    print("Organization bootstrapped.")
    print("-" * 64)
    print(f"  organization : {result.organization.name}  ({result.organization.public_id})")
    print(f"  owner        : {result.owner.email}  ({result.owner.public_id})")
    print(f"  api key      : {result.api_key.name}  ({result.api_key.public_id})")
    # Printed always, and loudly when it is not the default: an operator
    # who meant to create a benchmark tenant and got a customer one has
    # started attributing our own traffic to revenue, and usage events
    # are append-only.
    print(f"  usage origin : {origin.value}")
    if origin is not DEFAULT_TENANT_ORIGIN:
        print("                 NOT rated, and excluded from commercial analytics by default")
    print("-" * 64)
    print("  YOUR API KEY - shown once, never recoverable. Store it now:")
    print()
    print(f"      {result.generated.secret}")
    print()
    print("=" * 64)


async def _bootstrap_org(organization: str, email: str, name: str, usage_origin: str) -> None:
    # Parsed by the service, which owns the tenant vocabulary; the
    # entrypoint carries the operator's string and nothing more.
    origin = tenant_origin(usage_origin)
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
                usage_origin=origin,
            )
            # The CLI owns the commit: the service defined the atomic scope,
            # the entrypoint pulls the trigger (same split as the request scope).
            await session.commit()
        _print_bootstrap_result(result)
    finally:
        await engine.dispose()


async def _set_consent(organization_id: str, *, grant: bool, reference: str | None) -> None:
    """Grant or revoke a tenant's speech-data-collection consent.

    Same entrypoint contract as bootstrap: the service owns the rule and
    the atomic scope, the CLI owns the session and the commit.
    """
    settings = get_settings()
    configure_logging(settings)
    engine = create_engine(settings)
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            service = IdentityService(session, pepper=settings.auth.key_pepper.get_secret_value())
            if grant:
                organization = await service.grant_data_consent(
                    organization_public_id=organization_id, reference=reference
                )
            else:
                organization = await service.revoke_data_consent(
                    organization_public_id=organization_id
                )
            await session.commit()
    finally:
        await engine.dispose()
    state = "GRANTED" if organization.data_consent else "REVOKED"
    print(f"consent {state} for {organization.name} ({organization.public_id})")
    if organization.data_consent:
        print(f"  granted at : {organization.data_consented_at}")
        print(f"  reference  : {organization.consent_reference or '(none recorded)'}")
    elif organization.data_consented_at is not None:
        print(f"  last grant : {organization.data_consented_at} (historical record, retained)")


def _print_erasure_report(report: ErasureReport, *, heading: str) -> None:
    print()
    print("=" * 64)
    print(heading)
    print("-" * 64)
    print(f"  organization        : {report.organization_public_id}")
    print(f"  samples erased      : {report.samples_erased}")
    print(f"  audio objects gone  : {report.audio_objects_deleted}")
    print(f"  manifests revoked   : {report.manifests_revoked}")
    if report.datasets_deleted:
        print(f"  datasets deleted    : {report.datasets_deleted}")
    if report.api_keys_revoked:
        print(f"  api keys revoked    : {report.api_keys_revoked}")
    if report.memberships_removed:
        print(f"  memberships removed : {report.memberships_removed}")
    if report.organization_anonymized:
        print("  organization row    : anonymized and KEPT (usage ledger law)")
    for sample_id in report.erased_sample_ids:
        print(f"    erased: {sample_id}")
    print("=" * 64)


async def _erase(
    *,
    organization: str,
    sample: str | None = None,
    user_identifier: str | None = None,
    whole_organization: bool = False,
) -> None:
    """Run one erasure verb against the configured database AND object
    store. The storage seam is built unconditionally — the collection
    kill switch gates NEW collection, never the ability to erase what an
    earlier deployment already stored."""
    from intelliai_api.storage import S3ObjectStorage

    settings = get_settings()
    configure_logging(settings)
    engine = create_engine(settings)
    storage = S3ObjectStorage(settings.storage)
    try:
        factory = create_session_factory(engine)
        async with factory() as session:
            service = ErasureService(session, storage)
            if whole_organization:
                report = await service.erase_organization(organization_public_id=organization)
                heading = "Organization erased (data removed; ledger retained)."
            elif sample is not None:
                report = await service.erase_sample(
                    organization_public_id=organization, sample_public_id=sample
                )
                heading = "Speech sample erased."
            elif user_identifier is not None:
                report = await service.erase_user_data(
                    organization_public_id=organization, user_identifier=user_identifier
                )
                heading = f"User data erased ({user_identifier})."
            else:  # pragma: no cover - argparse guarantees one mode
                raise ValueError("erase requires a sample, a user identifier, or --org mode")
            # Objects are already gone (irreversibly); committing the row
            # deletions is what makes the database agree with the store.
            await session.commit()
        _print_erasure_report(report, heading=heading)
    finally:
        await storage.close()
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
    bootstrap.add_argument(
        "--usage-origin",
        default=DEFAULT_TENANT_ORIGIN.value,
        choices=TENANT_ORIGINS,
        help=(
            "why this tenant's traffic exists (default: %(default)s). Anything "
            "other than 'customer' is metered but never rated, and is excluded "
            "from commercial analytics by default. Set it at creation: usage "
            "events are append-only and cannot be reattributed."
        ),
    )

    grant = subcommands.add_parser(
        "grant-consent",
        help="Record a tenant's explicit opt-in to speech data collection",
    )
    grant.add_argument("--org", required=True, help="organization public id (org_...)")
    grant.add_argument(
        "--reference",
        default=None,
        help="the governing consent document (e.g. 'cohort-2026-08-consent-v1')",
    )

    revoke = subcommands.add_parser(
        "revoke-consent",
        help="Withdraw a tenant's data-collection consent; collection stops immediately",
    )
    revoke.add_argument("--org", required=True, help="organization public id (org_...)")

    erase_sample = subcommands.add_parser(
        "erase-sample",
        help="Permanently erase one speech sample: audio object, row, events, memberships",
    )
    erase_sample.add_argument("--org", required=True, help="organization public id (org_...)")
    erase_sample.add_argument("--sample", required=True, help="sample public id (smp_...)")

    erase_user = subcommands.add_parser(
        "erase-user-data",
        help=(
            "Erase every sample one identity contributed (a person's deletion "
            "request under the one-key-per-person convention)"
        ),
    )
    erase_user.add_argument("--org", required=True, help="organization public id (org_...)")
    erase_user.add_argument(
        "--user-identifier", required=True, help="the identity stamped on the samples (key_...)"
    )

    erase_org = subcommands.add_parser(
        "erase-org",
        help=(
            "Erase a whole tenant's collected data and datasets; keys revoked, "
            "org row anonymized and kept (usage ledger is retained by law)"
        ),
    )
    erase_org.add_argument("--org", required=True, help="organization public id (org_...)")
    erase_org.add_argument(
        "--yes",
        action="store_true",
        help="required: tenant erasure is irreversible",
    )

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
        if args.command == "grant-consent":
            asyncio.run(_set_consent(args.org, grant=True, reference=args.reference))
            return 0
        if args.command == "revoke-consent":
            asyncio.run(_set_consent(args.org, grant=False, reference=None))
            return 0
        if args.command == "erase-sample":
            asyncio.run(_erase(organization=args.org, sample=args.sample))
            return 0
        if args.command == "erase-user-data":
            asyncio.run(_erase(organization=args.org, user_identifier=args.user_identifier))
            return 0
        if args.command == "erase-org":
            if not args.yes:
                print(
                    "erase-org is irreversible: re-run with --yes to confirm.",
                    file=sys.stderr,
                )
                return 1
            asyncio.run(_erase(organization=args.org, whole_organization=True))
            return 0
        asyncio.run(
            _bootstrap_org(args.org_name, args.owner_email, args.owner_name, args.usage_origin)
        )
    except IntelliAIError as exc:
        print(f"error [{exc.code}]: {exc.message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
