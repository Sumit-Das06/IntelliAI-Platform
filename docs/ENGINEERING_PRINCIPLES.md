# Engineering Principles

The philosophy behind every decision in this repository. When two options
are both defensible, these principles break the tie. Each links to where
it's already visible in the codebase.

**1. The contract is the product.** Public API shapes, the error envelope,
and the internal runtime contract are frozen interfaces; models, providers,
and infrastructure churn freely behind them. When forced to choose between
a better implementation and a stable contract, the contract wins.
*(ADR-0003, ADR-0009, PRD §8)*

**2. Boring technology; complexity must earn its place.** Postgres does
triple duty (records, queue, ledger) because every additional stateful
system is an operational tax paid forever. New infrastructure requires a
named pain and written graduation criteria — see ADR-0006's rejection of
Celery. Innovation budget is spent on the product, not the plumbing.

**3. Standards are machines, not prose.** A rule that isn't enforced by
ruff, mypy, a hook, CI, a schema, or a test is a suggestion. When you make
a rule, build its enforcement; when you read a document repeating a
machine-checked rule, delete the document's copy.

**4. Fail fast at startup; degrade gracefully at runtime.** A process with
bad config must die before accepting traffic (Settings validation); a
process with a failing non-critical dependency must keep serving and say so
(degraded health). Never invert these.

**5. Everything is organization-scoped.** Tenancy is not a feature; it's
the coordinate system. Data, keys, quotas, metrics, logs — all carry the
org. An unscoped tenant query is a security bug, not a style issue.
*(ADR-0010)*

**6. Processes are disposable; state lives in Postgres/Redis/object
storage.** Any container may be killed at any moment. If losing a process
loses data, the design is wrong.

**7. Explain before building.** Significant decisions get an ADR *before*
implementation; new modules get their charter (why they exist, what they
own, what they must never own) at birth. Code tells you how; only writing
tells you why.

**8. Clean-machine reproducibility.** A fresh clone plus documented commands
must produce a working platform — locked dependencies, migrations from
zero, env-only config. CI re-proves this on every push; anything that only
works on one laptop is broken.

**9. Honest engineering.** Failures are reported plainly (the red CI run
stays in history), performance numbers say what they actually measure, and
"done" means verified — not "should work". Optimism is not a debugging
strategy.

**10. Optimize for the reader, then the maintainer, never the author.**
Code is read hundreds of times and written once. Boring, explicit,
greppable code beats clever code; a module a stranger can navigate beats
one its author loves.
