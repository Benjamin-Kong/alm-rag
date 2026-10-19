# M1 foundation design

This elaborates the approved SRS/SAD without changing their scope.

- SQLite connection per operation, foreign keys on, WAL, busy timeout, `BEGIN IMMEDIATE` for writes, versioned transactional migrations. Canonical UUIDv5 identities encode ordered source components as JSON; names never define identity.
- Storage includes instance/project/source-kind profiles, immutable revisions and owned active pointers, generation/chunk staging schema, rate state, failed attempts, jobs/checkpoints. M4 owns actual search publication.
- Queue is global FIFO, one RUNNING lease with random fencing token, lease expiry recovery and durable checkpoint. Stale workers cannot renew/checkpoint/finish. External side effects require stage idempotency; M1 has no live stage handlers. Unsupported public stages return 409.
- Admin is bootstrapped by local CLI using password input, Argon2 hash. Sessions/API keys are random and stored as hashes; sessions expire. Cookie is Secure/HttpOnly/SameSite=strict. Unsafe cookie requests require configured Origin and session-bound CSRF token (separate readable CSRF cookie). Login is 204 with cookies only. API keys have explicit project grants and operation permissions; no implicit wildcard from empty scopes.
- Credentials use authenticated encryption with master key supplied separately through environment. Stored raw source and secret values never enter diagnostic/audit events. Logging uses an allowlist and bounded safe identifiers; validation errors suppress input values.
- Public base path `/api/v1`. M1 implements auth/key/project/job diagnostics and health. OpenAPI draft retains future endpoints and marks implemented subset; executable OpenAPI snapshot and TS client must be consistent. Readiness checks local schema without probing ALM or external services.
- Ollama/Qdrant settings accept local/remote HTTP(S), explicit TLS/secret references; M1 only validates configuration and exposes no raw credentials.
- API and worker share the same non-root Python container. React foundation is separately built; no registration wizard. Default Docker ports bind loopback. No production secrets or ALM content in build context.

Security tests include missing/revoked keys, cross-project UID access, read/manage permissions, cookie CSRF, secret/log non-disclosure, expiry and stale lease fencing. Database tests use temporary files and no production data.
