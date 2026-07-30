"""Service layer — the business rules of the platform.

Charter: one service owns one business capability. Services orchestrate
repositories, define the atomic scope of operations (no partial commits —
the commit trigger belongs to the entrypoint's lifecycle: request scope,
CLI, worker), validate and normalize inputs, raise typed platform errors
(``core.errors``), and emit domain events (``entity.action``).

Services must never: contain SQL or import sqlalchemy statements, know
about HTTP, or render errors. If a sentence about the code contains
"WHERE", it belongs in a repository; if it contains "means" or "must",
it belongs here.
"""
