# infra/ — Infrastructure

- `docker/`  — one Dockerfile per deployable (`api.Dockerfile`, …), multi-stage,
               non-root users.
- `compose/` — compose overlays: `gpu` (device reservations), `prod`
               (no bind mounts, no published DB ports). The base
               `docker-compose.yml` lives at repo root for `make up` ergonomics.

No application logic here, ever.
