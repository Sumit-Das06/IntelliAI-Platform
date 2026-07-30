"""Repository layer: the only code allowed to write SQLAlchemy queries.

Contract (enforced in review):

- One repository per aggregate: ``OrganizationRepository``, ``UserRepository``,
  ``ApiKeyRepository``, ``JobRepository``, ``UsageRepository``,
  ``ModelRepository``, ``DatasetRepository``, ``ExperimentRepository``, …
- Repositories **receive** an ``AsyncSession``; they never create, commit, or
  roll one back — transaction boundaries belong to the caller (today the
  request scope, later possibly a Unit of Work).
- Repositories return entities or domain values, never raw ``Row``/``Result``.
- Every query on tenant-owned data takes organization scope explicitly —
  an unscoped query on a tenant table is a review-blocker (multi-tenancy
  isolation lives here, and later PostgreSQL RLS backs it up).
- Services depend on repositories; routers on services; **nothing above this
  package imports sqlalchemy**.

There is deliberately no abstract base repository: three concrete classes
share a constructor and nothing else worth abstracting yet — a base class
gets extracted when duplication demands it, not before.
"""

from intelliai_api.db.repositories.api_keys import ApiKeyRepository
from intelliai_api.db.repositories.organizations import OrganizationRepository
from intelliai_api.db.repositories.users import UserRepository

__all__ = ["ApiKeyRepository", "OrganizationRepository", "UserRepository"]
