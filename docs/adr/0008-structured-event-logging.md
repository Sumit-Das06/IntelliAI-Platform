# ADR-0008: Structured event logging with platform-wide correlation IDs

- **Status:** Accepted
- **Date:** 2026-07-29
- **Related:** ADR-0009

## Context

A multi-service platform is debugged through its logs; billing disputes,
support tickets, and incident response all hinge on reconstructing what
happened to one request across processes. Free-text logs cannot be queried,
and per-service log formats cannot be joined.

## Problem

What is the platform-wide logging contract — shape, fields, correlation,
and secrecy rules?

## Decision

We will log structured events via structlog: stable `event` names with
metadata fields, never prose. JSON-lines to stdout in production, pretty
console in dev — same call sites. Every entry carries timestamp, level,
event, service, service_version, environment, plus contextvars-bound
request context (`request_id` today; org/user/key/model IDs as they exist).
`X-Request-ID` is minted/echoed by gateway middleware, returned to clients,
and propagated to inference services as the platform correlation ID. A
processor redacts credential-shaped keys; `print()` is a lint error (ruff
T20). Application logs, audit logs, and usage events are three separate
systems with different guarantees and stores.

## Alternatives considered

- **stdlib logging + JSON formatter** — rejected: no processor pipeline,
  painful context binding, every service reinvents the format.
- **loguru** — rejected: pleasant ergonomics, second-class structured
  fields and ecosystem bridges.
- **OpenTelemetry-first** — deferred: heavier machinery than a pre-traffic
  platform needs; our primitives (stdout JSON, processors, contextvars) are
  exactly OTel-compatible when M10 arrives.

## Trade-offs

- structlog configuration is process-global — the accepted exception to the
  no-global-state rule.
- Key-name-based redaction cannot catch secrets embedded in free-text
  values; primary defense remains `SecretStr` discipline (never log bodies).

## Consequences

- Any log line answers "which request, which org, which service, when".
- Dashboards/alerts key on stable event names — renaming an event is a
  breaking change to observability and is treated like one.
- Loki/CloudWatch ingestion is deployment config, zero code.

## Future review criteria

- M10 observability: add OTel trace/span IDs via one processor; `request_id`
  stays customer-facing.
- Log volume cost at scale → sampling for success-path events; never sample
  errors.
