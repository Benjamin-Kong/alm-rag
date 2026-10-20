# Main implementation TDD evidence

Commands ran in the repository with Python 3.12.12 (`.venv/bin/python`). All test data are synthetic. Initial import errors are recorded as module-absence Red evidence, not falsely described as executed assertions.

| Slice | Requirements | Red command/result before implementation | Green result |
|---|---|---|---|
| Settings / secrets / auth core | SRS-017/027/028/038/044/057 | `-m pytest tests/test_security.py tests/test_config.py -q`: exit 2, two ModuleNotFoundError collection errors for security/config | Same command exit 0, 5 passed |
| API auth and project scope | SRS-019/027/028/040/057 | `-m pytest tests/test_api.py -q`: exit 2, missing almrag.api | API+security+config regression exit 0, 9 passed |
| Offline probes / worker shell | SRS-017/026/038/040/057 | `-m pytest tests/test_runtime.py -q`: exit 2, missing almrag.services | Runtime+API+security+config exit 0, 11 passed |
| Container prerequisites | SRS-051/052/059 | `-m pytest tests/test_deployment.py -q`: exit 1, draft backend lacks uv.lock/--frozen | Pending actual deployment edit and build/boot |

API unit tests use a minimal synthetic SQLite adapter. They do not replace integration tests against actual migrations/queue. Secret tests exercise encryption, wrong-key rejection, password/session/key hashing, expiry, revoke and diagnostic allowlisting. API tests exercise Secure/HttpOnly cookies, CSRF, invalid-body non-disclosure, permission checks, cross-project/missing job indistinguishability, revocation and scoped system_admin anti-escalation.

Observed test warning: installed Starlette's TestClient reports httpx integration deprecation (suggesting httpx2). Tests executed successfully; no dependency migration is inferred from a warning alone.

## Preliminary QA correction cycle 1

- QA found auth lookup/audit SQLite exceptions escaped the standardized error boundary (Medium). Added `test_database_auth_failure_is_sanitized` for each path: actual run produced **2 failed / 6 passed**, with injected OperationalError. Expanded the try boundary; API+runtime+security+config suite then **15 passed**.
- Added wrong-CSRF, cross-session CSRF, wrong-Origin, mixed bad API key + valid cookie, and scoped key revoke tests. These passed against existing rejection logic.
- Added assertion that CSRF denials are audited: actual **1 failed** (0 FORBIDDEN events). Implemented sanitized denial audit; combined suite **15 passed**.
- Added OpenAPI security/error contract assertion: actual **1 failed** (missing securitySchemes). Added explicit executable contract metadata; API suite **9 passed**.
- Docker prerequisite Red was fixed with digest-pinned images, frozen runtime install, non-root and health configuration: **1 passed**. Real build/boot remains separate evidence.

## Integration and final QA correction cycle 2

- Actual storage integration additions first produced 3 failed / 7 passed (missing parent directory, URL-derived instance UID and invalid cross-project failure reference). Fixed with private parent creation, persisted random instance UUID, ownership constraints; combined suite 29 passed.
- Real worker/API test first failed on absent persisted BLOCKED reason, then on missing job events endpoint. Implemented both; 33 tests passed.
- Independent QA found audit actor/target omitted. Added trace/actor/target and scoped-caller tests: 2 actual failures (unsupported trace argument and absent actor_ref). Added hashed caller reference, target UUID, request trace and transactional mutation+audit rollback; 34 tests passed.
- Added executable/exported OpenAPI parity test: PASS; it verifies artifact drift rather than introducing behavior.
- After npm installation the baseline validator incorrectly parsed vendor invalid-YAML fixtures. Added temporary copied-package regressions: 2 failed / 1 passed. Pruned only dependency/build/worktree dirs, kept authored YAML validation (including .yml); all 3 passed and DOC_STATIC_PASS restored.
- Final Main and independent QA runs: **38 Python tests PASS**, one dependency deprecation warning. No test skips/xfails.
