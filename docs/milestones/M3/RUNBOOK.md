# M3 local reproduction and operator runbook

M1/M2 approved; M3 pending its own Human Gate. The commands below recreate synthetic local evidence. They do not authorize live ALM/model traffic, M4, production deployment, Push or Notion transmission. Use Python3.12 and Node22; this host's bare Python3.9 lacks tomllib and its system Node25 has a broken dylib.

## Native checks

```sh
uv sync --frozen
.venv/bin/python tools/validate_baseline.py
.venv/bin/pytest -q
.venv/bin/python tools/export_openapi.py
export PATH="/opt/homebrew/opt/node@22/bin:$PATH"
npm --prefix frontend ci
npm --prefix frontend run generate:api
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend audit --audit-level=moderate
uv build
.venv/bin/python tools/smoke_m3.py
```

Current executed contract is docs/api/m3-openapi.json; m1-openapi.json and m2-openapi.json are historical. The draft superset marks implementation status and still includes unavailable routes. Public failed-item/replay remains deferred (OI-029). No M5 wizard dependency.

## Offline containers

```sh
docker --context colima-alm-rag build -f deploy/Dockerfile.backend -t almrag-api:m3 .
docker --context colima-alm-rag build -f deploy/Dockerfile.frontend -t almrag-frontend:m3 .
env DOCKER_CONTEXT=colima-alm-rag docker-compose -p almrag-m3-smoke -f deploy/compose.yaml up --no-build -d --wait --wait-timeout 90
docker --context colima-alm-rag run --rm -i --network none --entrypoint python almrag-api:m3 - < tools/smoke_m2.py
docker --context colima-alm-rag run --rm -i --network none --entrypoint python almrag-api:m3 - < tools/smoke_m3.py
env DOCKER_CONTEXT=colima-alm-rag docker-compose -p almrag-m3-smoke -f deploy/compose.yaml stop
```

Standalone docker-compose is used because this host lacks the Docker Compose plugin. CI uses the plugin on GitHub's runner; remote CI has not run. Smoke programs create temporary synthetic data, actual local WordLevel artifacts and mocked model responses. M3 smoke emits55chunks/13content requests/repeat0/FIXTURE_ONLY. Named smoke volume is retained on stop. Backend/Worker UID10001 and Frontend UID101. No destructive DB cleanup or production migration is authorized.

## Configuration and service boundary

The process reads explicit environment variables via Settings.from_env; `.env.example` is documentation, not an automatic dotenv loader. Database path uses ALMRAG_DATABASE_PATH. New model settings:

- ALMRAG_MODEL_PROFILE_PATH: optional local JSON manifest. No path means MODEL_PROFILE_UNCONFIGURED. Relative tokenizer_path resolves from manifest directory.
- ALMRAG_LIVE_MODEL_ENABLED: false by default; true allows model HTTP only after separate operator authorization. Merely supplying a profile cannot claim VERIFIED.
- ALMRAG_OLLAMA_BASE_URL, ALMRAG_OLLAMA_AUTH_REF (env:NAME/vault:reference), ALMRAG_CA_BUNDLE: URL, referenced credentials and trusted CA, separate from source credentials. TLS verification is enabled by default. No inline token/password belongs in a manifest.

Manifest shape is `{ "model": { "model_name": "embeddinggemma-2", "expected_digest": "sha256:<actual 64 hex digest>", "vector_dimension": 768, "effective_max_input_tokens": 1024 }, "tokenizer_path": "tokenizer.json", "tokenizer_sha256": "<actual 64 hex artifact checksum>" }`. Placeholder values are deliberately not a usable verified profile. Pin actual installed artifact/digest/dimensions/context; catalog prose is not runtime evidence. No model/tokenizer auto download.

The local tokenizer verifies source checksum, disables saved truncation/padding in memory, retains special tokens and versions its identity. Runtime verifies server digest/capability/context, two calibration inputs, vector dimensions/finite values and returned exact token counts. Every content embed uses truncate:false, checks input count and model digest before/after. Cached vectors still require validated ownership/fingerprint/integrity. Mock transports always remain FIXTURE_ONLY. Real model quality/tokenizer equivalence/operational limits remain NOT VERIFIED until actually measured; short calibration is not a proof for all possible strings.

A changed tokenizer identity/model/config requires new processing results; old derived artifacts are retained and not activated. Stop prototype workers before upgrading. Additive migrations1..4 run transactionally. Actual data migration/cleanup/destruction remains separately reviewed. No active revision/Qdrant/index is written in M3.

## Processing via CLI/REST without UI

With an existing approved HTTPS API session or correctly scoped API key, commands target the same routes tested by mock E2E:

```sh
almrag configure-processing PROJECT_UID /path/to/policy.json
almrag processing-preflight PROJECT_UID
almrag process PROJECT_UID --config-revision REVIEWED_FINGERPRINT
almrag processing-preflight PROJECT_UID
almrag embed PROJECT_UID --config-revision REVIEWED_FINGERPRINT
almrag jobs
```

Policy example: `{ "fields": [{"kind":"NORMALIZED","key":"title"},{"kind":"NORMALIZED","key":"description"},{"kind":"SOURCE","key":"original-field-id"}], "scope_fields": {"original-scope-id":[{"kind":"NORMALIZED","key":"description"}] } }`. fields:null inherits; fields:[] deliberately selects none. Instance defaults are admin-session-only PUT /api/v1/alm-instances/{uid}/processing-defaults; project GET/PUT processing-config uses existing project_read/project_manage grants. Normalized title/description never alias original catalog IDs.

Processing-preflight is distinct from the M2 source preflight; it uses stored latest revisions and makes no ALM calls. It pins effective field policy, source revisions, model/tokenizer/processor fingerprints and token limits. Stale submissions are rejected. Until explicitly authorized/calibrated runtime exists it is BLOCKED, including PROCESS because correct chunks require the matched token counter. EMBED requires prepared results for all pinned selected Items. PROCESS local errors leave ready siblings intact and record actual stage/revision; global integrity/auth/storage/lease errors stop. Remaining failed Item replay is M4 and no public replay endpoint is invented.

Worker handles COLLECT/PROCESS/EMBED; SYNC/INDEX/REBUILD_INDEX remain409. Worker independently renews its lease. A reclaimed EMBED job reuses committed verified vector-cache entries, never marks an incomplete result EMBED_READY and never switches the active search version. Hard OS process kill during real-model socket I/O is not yet measured.
