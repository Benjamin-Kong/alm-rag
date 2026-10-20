# M2 local runbook

M1 is user-approved. M2 is a local/mock approval candidate; actual ALM, production deployment and remote Push require separate approval. M3 processing/indexing is not available. Source sockets default to disabled; the commands below do not authorize live server access.

## Reproduce local evidence

```sh
uv sync --frozen
.venv/bin/python tools/validate_baseline.py
.venv/bin/python -m pytest -q
.venv/bin/python tools/export_openapi.py
export PATH="/opt/homebrew/opt/node@22/bin:$PATH"
npm --prefix frontend ci
npm --prefix frontend run generate:api
npm --prefix frontend test
npm --prefix frontend run build
```

M2 contract: docs/api/m2-openapi.json. M1 snapshot is historical and preserved. Main draft OpenAPI marks each implemented operation separately; search, replay and later-stage operations remain draft. Package dependencies did not change from M1; use the committed locks. Global Node25 is still broken locally (OI-034); select Node22 as above.

## CLI administration without a wizard

The CLI calls the same REST routes and enforces the same authorization. Administrator source registration/discovery requires an existing admin session; project operations also accept a properly scoped API key. No API key may administer global source profiles. An approved HTTPS API endpoint is required for sessions. The Compose HTTP health/proxy smoke below does not establish HTTPS admin-session operation.

Set ALMRAG_API_URL to the approved HTTPS console endpoint. `almrag login --username admin` prompts without echo and stores an API-URL-bound0600 session at data/client-session.json (or ALMRAG_SESSION_FILE); it never prints token/password. ALMRAG_SESSION_TOKEN plus ALMRAG_CSRF_TOKEN may instead be supplied from an OS secret store/environment. ALMRAG_API_KEY takes priority when supplied. Credentials are never accepted inline in source JSON; only env:NAME or vault:reference.

Command sequence after a separately authorized server connection is available:

```sh
almrag register-source /path/to/profile.json
almrag discover-projects INSTANCE_UID
almrag discover-scopes INSTANCE_UID SOURCE_PROJECT_ID
almrag discover-fields INSTANCE_UID SOURCE_PROJECT_ID
almrag register-project /path/to/project.json
almrag configure-collection PROJECT_UID /path/to/scope.json
almrag preflight PROJECT_UID
almrag collect PROJECT_UID --config-revision REVIEWED_FINGERPRINT
almrag jobs
```

Synthetic profile shape: source_type codebeamer or polarion, display_name, base_url, auth_ref, api_profile (cb-rest-v3 or polarion-rest-v1), http_policy. Project JSON: alm_instance_uid, source_project_id, name, scope_kind TRACKER/WORK_ITEM_TYPE, selection_mode ALL/SELECTED, source_scope_ids, embedding_fields. Source catalog IDs remain original; normalized title/description are separate capabilities. Full source fields are retained regardless of future embedding-field selection.

Preflight collect_ready does not imply sync_ready. estimated_requests is null/request_estimate_kind UNKNOWN because attachment/pages/retries are not known; request_count_lower_bound includes mandatory detail calls only. A changed field/scope/rate fingerprint rejects stale submission. COLLECT rescans conservatively and reuses immutable observations; full SYNC/PROCESS/EMBED/INDEX stay409. No active revision is published. Failed-item list/replay API stays deferred under OI-029.

## Containers and offline smoke

Use the dedicated local Colima context and a distinct test Compose project. The installed Docker CLI lacks its Compose plugin; standalone docker-compose works. M2 images can be built with plain docker build. No dependency version update was necessary.

```sh
docker --context colima-alm-rag build -f deploy/Dockerfile.backend -t almrag-api:m2 .
docker --context colima-alm-rag build -f deploy/Dockerfile.frontend -t almrag-frontend:m2 .
env DOCKER_CONTEXT=colima-alm-rag docker-compose -p almrag-m2-smoke -f deploy/compose.yaml up --no-build -d --wait --wait-timeout 90
docker --context colima-alm-rag run --rm -i --network none --entrypoint python almrag-api:m2 - < tools/smoke_m2.py
env DOCKER_CONTEXT=colima-alm-rag docker-compose -p almrag-m2-smoke -f deploy/compose.yaml stop
```

Backend/Worker UID10001; Frontend UID101. Database and default attachments share /app/data volume; ALMRAG_ATTACHMENT_ROOT overrides the asset path consistently in API/Worker. Canonical SQLite sibling lock directories must be shared by all workers on a lock-capable filesystem. Never delete lockfiles while workers run. Equivalent host case/default443/80 uses one origin/budget. This does not prove distinct DNS aliases or distributed filesystem coordination.

Stop prototype workers before upgrading. Noncanonical old transport budgets deliberately fail closed with SERVER_ORIGIN_MIGRATION_REQUIRED; no automatic merge/deletion/active-lock relocation is attempted. Review any real persisted-state migration separately. Runtime smoke only creates temporary synthetic SQLite/assets. Test volumes are retained on stop; no destructive DB cleanup is part of this runbook.

## Retained limitations

Actual ALM versions/permissions/TLS, operational rate limits, wiki POST safety, confirmed production deletion and processed HTML fidelity are NOT VERIFIED. Live renderer stays disabled. Missing/404/out-of-scope never proves deletion; generic evidence-guarded deletion is tested with stubs only. Search exclusion/publication remains M4. Chunking/embeddings, public failed-item replay and M5 wizard remain unimplemented. Logical deadlines reject late responses; hard interruption of a blocked synchronous socket read is not proven.
