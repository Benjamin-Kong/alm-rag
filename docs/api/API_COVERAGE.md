# REST API coverage and open questions (v0.3)

Every path is a **DRAFT CONTRACT** only. Endpoints and `x-required-scope` do not implement authorization.
An API Key must carry project scope and operation permission; admin cookie authentication requires CSRF protection. Authentication and authorization must be enforced server-side for each route, including paths carrying only job_id or item_uid.
Broad 200/202 responses are placeholders, NOT full request/response schemas; M1 and M5 must finalize OpenAPI models through TDD.

| Method | Path | Operation ID | Required scope |
|---|---|---|---|
| POST | `/search` | `searchItems` | `search` |
| POST | `/projects/{project_uid}/sync` | `startSync` | `project_manage` |
| GET | `/jobs/{job_id}` | `getJob` | `project_read` |
| POST | `/alm-instances` | `registerAlmInstance` | `system_admin` |
| POST | `/alm-instances/{instance_uid}/probe` | `probeAlmInstance` | `system_admin` |
| GET | `/alm-instances/{instance_uid}/projects` | `discoverAlmProjects` | `system_admin` |
| GET | `/alm-instances/{instance_uid}/projects/{source_project_id}/scopes` | `discoverCollectionScopes` | `system_admin` |
| PUT | `/projects/{project_uid}/collection-config` | `configureCollectionScope` | `project_manage` |
| POST | `/projects/{project_uid}/preflight` | `preflightProject` | `project_manage` |
| PUT | `/alm-instances/{instance_uid}/rate-policy` | `setServerRateLimit` | `system_admin` |
| GET | `/jobs/{job_id}/failed-items` | `listFailedItems` | `project_read` |
| POST | `/jobs/{job_id}/failed-items/{item_uid}/retry` | `retryFailedItem` | `project_manage` |
| POST | `/jobs/{job_id}/failed-items/retry` | `retryFailedItems` | `project_manage` |
| POST | `/jobs/{job_id}/resume` | `resumeJob` | `project_manage` |
| POST | `/auth/login` | `adminLogin` | `public` |
| POST | `/auth/logout` | `adminLogout` | `authenticated` |
| POST | `/api-keys` | `createApiKey` | `system_admin` |
| DELETE | `/api-keys/{key_id}` | `revokeApiKey` | `system_admin` |
| GET | `/projects` | `listProjects` | `project_read` |
| POST | `/projects/{project_uid}/jobs` | `startProjectStageJob` | `project_manage` |
| GET | `/jobs` | `listJobs` | `project_read` |
| GET | `/projects/{project_uid}/items` | `listProjectItems` | `project_read` |
| GET | `/items/{item_uid}` | `getItemDetail` | `project_read` |
| GET | `/items/{item_uid}/revisions` | `getItemRevisions` | `project_read` |
| GET | `/items/{item_uid}/chunks` | `getItemChunks` | `project_read` |
| POST | `/projects/{project_uid}/integrity` | `startIntegrityReport` | `project_manage` |
| POST | `/projects/{project_uid}/evaluations` | `startRetrievalEvaluation` | `project_manage` |
| POST | `/projects/{project_uid}/export` | `exportProject` | `project_manage` |
| POST | `/projects/{project_uid}/import` | `importProject` | `project_manage` |
| POST | `/backups` | `createBackup` | `system_admin` |
| GET | `/backups` | `listBackups` | `system_admin` |
| POST | `/backups/{backup_id}/restore` | `restoreBackup` | `system_admin` |
| GET | `/audit-events` | `listAuditEvents` | `system_admin` |
| GET | `/jobs/{job_id}/events` | `listJobEvents` | `project_read` |
| GET | `/healthz` | `healthz` | `public` |
| GET | `/readyz` | `readyz` | `system_admin` |

## Outstanding OpenAPI contract gaps
- Explicit pagination/filter/cursor and error body schemas for catalog and explorer.
- Audit/Backup/Import storage security, exception flow and idempotency keys.
- Per-item accepted/blocked stage dependencies, async job state transition policy.
- Admin session expiry, CSRF/origin policy, first-admin bootstrap, API key rotation and permission lattice.
- Rate policy and server credential injection never return secret values.
- Cross-project query must filter both lexical and vector stores before scoring and again at detail read.
- POST imports accept only staged local artifact references; never arbitrary server path or external URL.

## Required tests
- Unauthorized project_uid / job_id / item_uid cannot reveal data or timing details.
- Pagination for 100k Items stable under changes; `top_k` means distinct Items.
- OpenAPI schema validation and frontend generated client contract parity, M1/M5 gates.

## Security scheme policy
- OpenAPI OR-auth lists ApiKeyAuth or AdminSession; this describes identity methods only. Application permissions `x-required-scope` and per-Project ACL are obligatory in Backend business logic.
- AdminSession cookies require CSRF protection for unsafe methods; `/auth/login` and `/healthz` are public. Do not expose tokens/passwords in API responses or logs.
- REST 401/403/409 responses must use future ApiError schema; current descriptions are incomplete draft contracts.
- OpenAPI 3.0.3 does not represent the conditional `SELECTED => source_scope_ids minItems 1` rule natively; validate it in application-level schemas and contract tests.
