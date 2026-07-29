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

The first concrete repositories (and their abstract base, if one earns its
keep) arrive with the first entities in M1 — abstractions get extracted from
working code, not invented ahead of it.
"""
