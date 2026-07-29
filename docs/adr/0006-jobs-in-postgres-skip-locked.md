# ADR-0006: Batch jobs via Postgres `SKIP LOCKED`, not a queue framework

- **Status:** Accepted
- **Date:** 2026-07-29
- **Related:** ADR-0002, ADR-0010

## Context

Async batch work arrives in M5: hour-long audio transcriptions, later
training jobs. Job state is business data — customers query it (`GET
/v1/jobs/{id}`), billing depends on it, and it must be consistent with
usage records. The default industry reflex is Celery + Redis/RabbitMQ.

## Problem

What infrastructure carries queued work, and where does job state live?

## Decision

We will store jobs in a Postgres table and dispatch them to workers with
`SELECT … FOR UPDATE SKIP LOCKED`. Workers are plain processes polling with
bounded intervals. Redis remains cache and rate-limit state only. No Celery,
no broker.

## Alternatives considered

- **Celery + Redis broker** — rejected: job state becomes opaque broker
  payloads; enqueue-and-record requires dual writes with no shared
  transaction; a second stateful system to operate; debugging story is
  notoriously poor.
- **RabbitMQ** — rejected: real queue semantics we don't yet need, at the
  cost of another 24/7 stateful service.
- **Managed cloud queues (SQS…)** — rejected: breaks dev/prod parity and
  the no-proprietary-core-dependencies rule (PRD §7).

## Trade-offs

- Polling latency (bounded by poll interval, ~1 s) instead of push.
- Queue throughput ceiling well below dedicated brokers.
- ~100 lines of worker/dispatch code we own ourselves.

## Consequences

- Enqueueing a job, writing its usage record, and updating quotas can be
  one ACID transaction — no reconciliation jobs, ever.
- The queue is queryable with SQL: dashboards, support, and debugging get
  `SELECT * FROM jobs WHERE …` instead of broker introspection tools.
- One backup/restore story for all state.

## Future review criteria

Graduation signals to a dedicated broker (any sustained, not spiky):
- job insert rate approaching ~1k/min, or queue-poll load visibly degrading
  Postgres;
- multi-region workers needing locality-aware dispatch;
- genuine pub/sub or fan-out semantics required, not just work queues.
