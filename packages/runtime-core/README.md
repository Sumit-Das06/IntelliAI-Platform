# packages/runtime-core — Shared Runtime Lifecycle

The machinery every IntelliAI runtime is built from (ADR-0019), extracted
from the first runtime when the second consumer arrived: `ArtifactStore`
(hash-verified model files, downloaded once, trusted never), `WorkerPool`
(bounded admission, honest overload), `ModelManager` (measured
`ensure → load → warm-up → serve` lifecycle), and `RuntimeServiceError`
(the one failure type, contract-shaped).

**runtime-core owns lifecycle, never inference.** It knows `ensure`,
`load`, `warm`, `ready`, `execute`, `shutdown` — and has zero knowledge of
what any model does. Engines are opaque type parameters whose only
lifecycle requirement is `close()`; warm-up is a capability-defined
deterministic probe injected by each runtime. The boundary test suite
enforces this in CI: no foundation-model libraries, no capability
packages, no server transport, contract imports limited to error
vocabulary.
