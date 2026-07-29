# ADR-0010: Organizations-first tenancy from the first table

- **Status:** Accepted
- **Date:** 2026-07-29
- **Related:** ADR-0006, ADR-0009

## Context

IntelliAI is a commercial SaaS. Retrofitting organizations onto a
users-only schema is one of the most expensive migrations in SaaS history:
every table, query, and permission check revisited under load, with
customers watching. Today every "organization" will have exactly one
member — which is precisely why the cost of doing it now is trivial.

## Problem

Is the tenancy unit the user or the organization, and how is isolation
enforced?

## Decision

We will model tenancy as `organizations → memberships → users` from M1's
first migration. API keys belong to organizations, never users. Every
tenant-owned table carries `organization_id`. Isolation is enforced in the
repository layer — every query on tenant data takes explicit organization
scope; an unscoped query is a review-blocker — with PostgreSQL row-level
security to be layered on later as defense-in-depth. Public identifiers are
prefixed (`org_…`, `key_…`, `job_…`); internal PKs never leave the API.

## Alternatives considered

- **Users-only now, orgs later** — rejected: the migration this ADR exists
  to prevent.
- **Database-per-tenant** — rejected as default: real isolation, unpayable
  operational cost at our scale; the correct future *enterprise-tier
  add-on*, not the architecture.
- **Schema-per-tenant** — rejected: migration × N schemas pain, weak
  ecosystem support, none of database-per-tenant's compliance value.

## Trade-offs

- Two "extra" tables and a join, years before multi-member orgs matter.
- Every repository method carries an organization parameter forever.

## Consequences

- Teams, roles, and enterprise features are additive later, not structural.
- Metering, quotas, and billing aggregate naturally at the org level.
- The repository layer is the single audit point for tenant isolation
  (and the single place RLS session variables get set later).

## Future review criteria

- Enterprise deals demanding physical isolation → dedicated-database tier
  for those tenants, on top of this model, not instead of it.
- If RLS adoption (post-M6) shows repository-layer scoping gaps, RLS
  becomes mandatory rather than defense-in-depth.
