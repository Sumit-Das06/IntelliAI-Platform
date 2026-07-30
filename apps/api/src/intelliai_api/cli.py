"""Operational CLI for the IntelliAI platform.

Charter: entrypoint only — argument parsing, session lifecycle (including
the commit), and human-readable output. All business logic lives in
services; this module may never import repositories or models directly.

Usage (via Makefile):
    make bootstrap-org org="Acme" email="you@example.com" name="You"
"""

import argparse
import asyncio
import sys

from intelliai_api.core.config import get_settings
from intelliai_api.core.errors import IntelliAIError
from intelliai_api.core.logging import configure_logging
from intelliai_api.db.engine import create_engine, create_session_factory
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="intelliai", description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)

    bootstrap = subcommands.add_parser(
        "bootstrap-org", help="Create an organization with an owner and first API key"
    )
    bootstrap.add_argument("--org-name", required=True)
    bootstrap.add_argument("--owner-email", required=True)
    bootstrap.add_argument("--owner-name", required=True)

    args = parser.parse_args(argv)

    try:
        asyncio.run(_bootstrap_org(args.org_name, args.owner_email, args.owner_name))
    except IntelliAIError as exc:
        print(f"error [{exc.code}]: {exc.message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
