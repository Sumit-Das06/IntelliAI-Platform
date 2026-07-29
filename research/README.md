# research/ — Isolated Experimental Work

Exploratory experiments, ad-hoc model comparisons, notebooks. No production
quality bar applies here — that freedom exists BECAUSE of one hard rule:

**Production code must never import from `research/`. Ever.**

Research may depend on production components (packages, service APIs). Anything
research produces that production needs gets promoted: rewritten to production
standards inside `ml/` or `services/`, with tests and review.

- `experiments/` — model/technique explorations
- `benchmarks/`  — ad-hoc comparisons (the production harness lives in `ml/evaluation`)
- `notebooks/`   — Jupyter notebooks (outputs stripped before commit)
