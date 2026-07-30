"""Credential-library tests: every promise in ADR-0012, pinned.

Pure functions under test — no fixtures, no I/O, no mocks. If a test here
goes red, a security promise broke.
"""

import string

import pytest

from intelliai_api.core.security import (
    DISPLAY_PREFIX_CHARS,
    LIVE_NAMESPACE,
    RESERVED_NAMESPACES,
    GeneratedKey,
    generate_api_key,
    hash_api_key,
    is_well_formed,
    verify_api_key,
)

PEPPER = "unit-test-pepper"


# ── Generation ──────────────────────────────────────────────────────────


def test_generated_key_anatomy() -> None:
    key = generate_api_key(PEPPER)
    assert key.secret.startswith(LIVE_NAMESPACE)
    assert len(key.secret) == len(LIVE_NAMESPACE) + 43  # 256-bit urlsafe secret
    assert key.prefix == key.secret[:DISPLAY_PREFIX_CHARS]
    assert key.last4 == key.secret[-4:]
    assert key.hash == hash_api_key(key.secret, PEPPER)


def test_generated_secrets_use_urlsafe_alphabet_only() -> None:
    allowed = set(string.ascii_letters + string.digits + "-_")
    body = generate_api_key(PEPPER).secret.removeprefix(LIVE_NAMESPACE)
    assert set(body) <= allowed


def test_generated_keys_are_unique() -> None:
    secrets_seen = {generate_api_key(PEPPER).secret for _ in range(1000)}
    assert len(secrets_seen) == 1000


def test_reserved_namespaces_are_not_issuable() -> None:
    for namespace in RESERVED_NAMESPACES:
        if namespace == LIVE_NAMESPACE:
            continue
        with pytest.raises(ValueError, match="not issuable"):
            generate_api_key(PEPPER, namespace=namespace)


def test_unknown_namespace_rejected() -> None:
    with pytest.raises(ValueError, match="not issuable"):
        generate_api_key(PEPPER, namespace="ik_admin_")


# ── Shown-once semantics ────────────────────────────────────────────────


def test_repr_never_exposes_the_secret() -> None:
    key = generate_api_key(PEPPER)
    assert key.secret not in repr(key)
    assert key.secret not in str(key)


def test_generated_key_is_immutable() -> None:
    key = generate_api_key(PEPPER)
    with pytest.raises(AttributeError):
        key.secret = "tampered"  # type: ignore[misc]


# ── Hashing ─────────────────────────────────────────────────────────────


def test_hash_is_deterministic_and_hex_sha256_shaped() -> None:
    key = generate_api_key(PEPPER)
    first = hash_api_key(key.secret, PEPPER)
    second = hash_api_key(key.secret, PEPPER)
    assert first == second  # determinism = the O(1) lookup property
    assert len(first) == 64
    assert set(first) <= set(string.hexdigits.lower())


def test_different_pepper_produces_unrelated_hash() -> None:
    key = generate_api_key(PEPPER)
    assert hash_api_key(key.secret, PEPPER) != hash_api_key(key.secret, "other-pepper")


def test_hash_never_contains_secret_or_pepper() -> None:
    key = generate_api_key(PEPPER)
    assert key.secret not in key.hash
    assert PEPPER not in key.hash


# ── Verification ────────────────────────────────────────────────────────


def test_correct_key_verifies() -> None:
    key = generate_api_key(PEPPER)
    assert verify_api_key(key.secret, PEPPER, key.hash)


def test_single_character_tamper_fails() -> None:
    key = generate_api_key(PEPPER)
    last = key.secret[-1]
    flipped = "A" if last != "A" else "B"
    assert not verify_api_key(key.secret[:-1] + flipped, PEPPER, key.hash)


def test_wrong_pepper_fails_verification() -> None:
    key = generate_api_key(PEPPER)
    assert not verify_api_key(key.secret, "wrong-pepper", key.hash)


def test_empty_and_garbage_candidates_fail_without_error() -> None:
    key = generate_api_key(PEPPER)
    assert not verify_api_key("", PEPPER, key.hash)
    assert not verify_api_key("not-a-key", PEPPER, key.hash)


# ── Format validation ───────────────────────────────────────────────────


def test_generated_keys_are_well_formed() -> None:
    assert is_well_formed(generate_api_key(PEPPER).secret)


def test_reserved_namespace_keys_parse_as_well_formed() -> None:
    # A future ik_test_ key must not be rejected as garbage by old servers.
    fake_body = "A" * 43
    assert is_well_formed(f"ik_test_{fake_body}")


@pytest.mark.parametrize(
    "candidate",
    [
        "",
        "ik_live_",  # no secret
        "ik_live_" + "A" * 42,  # too short
        "ik_live_" + "A" * 44,  # too long
        "ik_live_" + "A" * 42 + "!",  # bad alphabet
        "sk_live_" + "A" * 43,  # not our vendor prefix
        "ik_admin_" + "A" * 43,  # unknown namespace
        "IK_LIVE_" + "A" * 43,  # case matters
    ],
)
def test_malformed_candidates_are_rejected(candidate: str) -> None:
    assert not is_well_formed(candidate)


def test_key_hash_fits_and_prefix_fits_storage_columns() -> None:
    """The schema (String(64)/String(16)/String(4)) and this module must agree."""
    key = generate_api_key(PEPPER)
    assert len(key.hash) == 64
    assert len(key.prefix) == 16
    assert len(key.last4) == 4


def test_generated_key_type_is_the_only_bundle() -> None:
    assert isinstance(generate_api_key(PEPPER), GeneratedKey)
