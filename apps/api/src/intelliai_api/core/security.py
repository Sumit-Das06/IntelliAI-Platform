"""API key cryptography — the platform's credential library (ADR-0012).

Charter: PURE functions over strings. No database, no HTTP, no framework
imports, no logging, no clock, no global state. This module answers exactly
one question — given an API key, how do we securely generate, hash, verify,
and identify it? — and nothing else. Lookup, storage, and error rendering
belong to callers.

Purity IS the security property: every function is deterministic in its
inputs, so the module is exhaustively testable and auditable by reading one
file top to bottom.

Key anatomy::

    ik_live_Uv3nT0k3nUrl5af3Chars…    (52 characters total)
    └─┬──┘└──────────┬──────────┘
   namespace   256-bit random secret (43 urlsafe-base64 chars)

Only ``ik_live_`` is issuable today; the other namespaces are RESERVED so
future key classes need no format migration and external parsers can trust
the pattern from day one.

STANDING INVARIANT (ADR-0012): the fast-hash scheme here is valid ONLY for
platform-generated high-entropy secrets. User-chosen credentials, if they
ever exist, take an Argon2id path — never this one.
"""

import hmac
import secrets
import string
from dataclasses import dataclass, field
from hashlib import sha256

LIVE_NAMESPACE = "ik_live_"
RESERVED_NAMESPACES: tuple[str, ...] = (
    LIVE_NAMESPACE,
    "ik_test_",  # reserved: test-mode keys
    "ik_service_",  # reserved: internal service-to-service keys
    "ik_temp_",  # reserved: short-lived delegated keys
)
_ISSUABLE_NAMESPACES = frozenset({LIVE_NAMESPACE})

_SECRET_BYTES = 32  # 256 bits of CSPRNG entropy
_SECRET_CHARS = 43  # length of token_urlsafe(32)
_URLSAFE_ALPHABET = frozenset(string.ascii_letters + string.digits + "-_")

# First 16 chars ("ik_live_" + 8) — safe to display and store for support.
DISPLAY_PREFIX_CHARS = 16


@dataclass(frozen=True)
class GeneratedKey:
    """The one-time bundle produced at key creation.

    ``secret`` is the full plaintext key: return it to the caller ONCE,
    then let it die — never persist or log it (``repr`` masks it for that
    reason). ``prefix``, ``last4``, and ``hash`` are what gets stored.
    """

    secret: str = field(repr=False)
    prefix: str
    last4: str
    hash: str


def generate_api_key(pepper: str, *, namespace: str = LIVE_NAMESPACE) -> GeneratedKey:
    """Mint a new API key in the given namespace.

    Raises ``ValueError`` for namespaces that are reserved but not yet
    issuable, or unknown entirely — generation is the single gate that
    keeps the standing invariant true.
    """
    if namespace not in _ISSUABLE_NAMESPACES:
        raise ValueError(
            f"namespace {namespace!r} is not issuable "
            f"(issuable: {sorted(_ISSUABLE_NAMESPACES)}; "
            f"reserved: {list(RESERVED_NAMESPACES)})"
        )
    secret = namespace + secrets.token_urlsafe(_SECRET_BYTES)
    return GeneratedKey(
        secret=secret,
        prefix=secret[:DISPLAY_PREFIX_CHARS],
        last4=secret[-4:],
        hash=hash_api_key(secret, pepper),
    )


def hash_api_key(secret: str, pepper: str) -> str:
    """HMAC-SHA256 over the full key string, keyed by the server pepper.

    Deterministic by design: the hash is the database lookup value
    (one indexed equality query at auth time). A database dump alone is
    useless without the pepper, which lives in a different security domain
    (environment, not database).
    """
    return hmac.new(pepper.encode(), secret.encode(), sha256).hexdigest()


def is_well_formed(candidate: str) -> bool:
    """Cheap structural check before any cryptography or database work.

    True iff the candidate uses a known namespace (including reserved
    ones — their keys parse fine, they just won't match any stored hash)
    with a correctly sized, correctly alphabeted secret. Lets the caller
    distinguish "malformed garbage" from "well-formed but unknown key"
    in its error codes.
    """
    for namespace in RESERVED_NAMESPACES:
        if candidate.startswith(namespace):
            body = candidate[len(namespace) :]
            return len(body) == _SECRET_CHARS and set(body) <= _URLSAFE_ALPHABET
    return False


def verify_api_key(candidate: str, pepper: str, stored_hash: str) -> bool:
    """Does ``candidate`` match ``stored_hash`` under ``pepper``?

    Constant-time comparison (``hmac.compare_digest``) — defense in depth
    on top of the indexed-lookup path, and the mandatory primitive anywhere
    a secret-derived value is compared.
    """
    return hmac.compare_digest(hash_api_key(candidate, pepper), stored_hash)
