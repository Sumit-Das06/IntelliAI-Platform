"""Contract version and public surface.

The version golden makes bumping CONTRACT_VERSION impossible to do by
accident; the surface test makes every promised export real.
"""

import intelliai_runtime_contract as contract
from intelliai_runtime_contract import CONTRACT_VERSION


def test_contract_version_is_exactly_one() -> None:
    # Bumping this number is a platform-wide breaking event (ADR-0016).
    # If you are editing this assertion, you must be superseding schemas
    # deliberately — additive changes never touch it.
    assert CONTRACT_VERSION == 1
    assert type(CONTRACT_VERSION) is int


def test_every_promised_export_exists() -> None:
    for name in contract.__all__:
        assert getattr(contract, name, None) is not None, name
