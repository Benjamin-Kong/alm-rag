# M1 local runbook

M1 is a foundation, not a working ALM collection/search product. Real stage requests return 409 STAGE_UNAVAILABLE. No ALM/embedding requests happen at startup.

## Native

```sh
uv sync --frozen
source .venv/bin/activate
python -m almrag.cli migrate
python -m almrag.cli bootstrap-admin
python -m almrag.api
# separate terminal, same database path:
python -m almrag.worker
```

`ALMRAG_DATABASE_PATH` defaults to data/alm.sqlite. API and worker require the same local filesystem/host; do not use NFS. Schema migration is idempotent. No default admin/password exists. First-admin bootstrap prompts without echo. Set `ALMRAG_MASTER_KEY` externally to a Fernet key before `python -m almrag.cli store-secret <opaque-ref>`; do not store the master key in the DB, repository or shared logs.

Browser login requires an HTTPS reverse proxy and `ALMRAG_ALLOWED_ORIGIN` matching that origin. Session cookies remain Secure/HttpOnly/SameSite=strict; POST requests need `X-CSRF-Token` from the separate CSRF cookie. The M1 frontend only displays public health and does not implement login or the M5 wizard. API keys can be supplied to CLI via `ALMRAG_API_KEY`, with optional `ALMRAG_API_URL`.

Readiness is `/api/v1/readyz`, requires system_admin and checks local database tables. It makes no external dependency health claim. Liveness `/api/v1/healthz` is public.

## Containers

```sh
docker-compose -p almrag-dev -f deploy/compose.yaml build
docker-compose -p almrag-dev -f deploy/compose.yaml up -d --wait
docker-compose -p almrag-dev -f deploy/compose.yaml down
```

On this machine use Docker context colima-alm-rag explicitly (or `DOCKER_CONTEXT=colima-alm-rag` for standalone Compose). Start the dedicated VM using the preflight runbook first. API/Frontend ports bind loopback 8000/8080; persistent volume is retained on ordinary down. Never remove a non-test data volume without separate approval.

API and worker share one Python image; frontend uses a separate non-root Nginx image. Dependency installs use uv.lock/package-lock.json and base image digests. The optional `services` profile provides Qdrant; to use it explicitly set ALMRAG_QDRANT_URL=http://qdrant:6333. Default services URLs target host.docker.internal; deployments may supply trusted local/remote URLs and CA/secret references. No public Qdrant or model service is required by M1 tests.

## Verification

```sh
uv run pytest -q
uv run python tools/validate_baseline.py
uv run python tools/export_openapi.py
cd frontend
npm ci
npm run generate:api
npm test
npm run build
```

Generated M1 API JSON is the executed subset; original OpenAPI retains unimplemented future routes with explicit statuses. Error responses suppress input values and raw DB/server exceptions. Product endpoints need both permission and project grant; system_admin API keys cannot grant themselves a larger scope. Global audit requires a browser admin session.

Native Windows and Linux, GitHub-hosted CI execution, real ALM compatibility and model/index integration require later execution evidence. CI configuration existing locally is not a remote CI PASS.
