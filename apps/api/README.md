# apps/api — API Gateway & Control Plane

The single entry point for all client traffic (FastAPI, async). Owns authentication,
API keys, rate limiting, usage metering, the model registry, job orchestration, and
routing to inference services. Domain-generic by design: nothing in here may be
speech-specific — that logic belongs to inference services.

Code arrives in Milestone 0, steps 3–8.
