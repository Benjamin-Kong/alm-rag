# M2 ALM Collectors

Status: PENDING_APPROVAL (2026-10-20). M1 remains approved. M2 known code findings corrected through3 review rounds; Main178 Python/7 Frontend tests and local container runtime pass. Independent QA177 full tests plus final new targeted regression pass. Initial connection/config prototype TDD chronology exception and external limits require user review. See QA_REPORT.md/COMPLETION.md. Base:13e1f30, branch codex/m2-collectors; authorization/design commit:2a934c5. M3 not started.

Primary15: SRS-001/003/004/005/006/007/008/010/022/045/046/047/053/054/055. Shared6: SRS-039/041/044/049/058/059. Primary/Shared assignments remain unchanged.

## Execution and ownership

1. Main records plan/design and additive migration contracts; actual Red tests precede each behavior.
2. ALM Collector specialist owns src/almrag/connectors/**, tests/test_connectors.py, sanitized fixture files under tests/fixtures/alm/** and CONNECTOR_TDD.md in an isolated .worktrees/m2-connectors checkout. Main owns transport, repository/pipeline, schema, API/CLI/client/docs and integration. No concurrent writer shares a file.
   Collection specialist separately owns src/almrag/collection.py, migrations/002_collection.sql, tests/test_collection.py and COLLECTION_TDD.md in .worktrees/m2-collection; subsequently owned worker.py/test_m2_worker.py/WORKER_TDD.md there. Transport repair specialist owns alm_http.py/test_alm_http.py/TRANSPORT_TDD.md in .worktrees/m2-transport. These frozen files have now been copied into Main with92 targeted tests PASS; complete REST/contract/CLI acceptance remains incomplete and full suite3FAIL/132PASS.
3. Requirements and architect specialists review read-only. QA independently runs/reviews after integration and does not modify implementation. Maximum3 fix/retest rounds; unresolved Critical/Major or policy changes stop for Human Review.
4. Mock matrix includes3 Codebeamer and3 Polarion projects; pagination, permissions, revisions, attachments, complete raw retention, source-specific scopes, shared pacing/429 and partial failure/restart tests.
5. Refresh OpenAPI, negative ACL tests, generated TS client and traceability together. Record PASS/FAIL/NOT VERIFIED. Request M2 approval and stop before M3.

## Boundaries

- No actual ALM connections, customer content, remote Push, deployment or Notion publishing. Runtime live-network enablement is off by default; mock transports are explicit injections.
- Support COLLECT; full SYNC remains409 until PROCESS/EMBED/INDEX exist. No active_revision_uid publication in M2.
- Source profile/Project/Tracker or Type registration and preflight are REST/CLI; no M5 wizard dependency.
- Renderer POST stays disabled unless the selected profile has explicit non-mutating contract evidence; real-server safety/compatibility remains NOT VERIFIED. Mock evidence never auto-enables a live profile.
- OI-029 failure-list/replay API permission conflict stays open; M2 persists failure queue and aggregate diagnostics, with full public replay deferred to its Primary milestone.
- Existing editor swap file is preserved and ignored; it is not an implementation artifact.

## Preflight

DOC_STATIC_PASS observed. Codex CLI0.163.0/multi_agent/worktrees verified using the project's Node22 PATH. Global Node25 currently aborts on missing simdjson dylib; no global relinking was performed. Track as OI-034. Requirements/architecture review identified v1 migration runner and pre-revision failure limitations; additive v2 addresses them without rewriting immutable records or dropping existing data.
