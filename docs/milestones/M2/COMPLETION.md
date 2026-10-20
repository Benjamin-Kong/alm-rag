# M2 ALM collection — approval candidate

Status: **PENDING_APPROVAL**, 2026-10-20. M1 was user-approved at13e1f30. M2 start/design authorization commit2a934c5 is on codex/m2-collectors. Subsequent user instructions authorized the recorded corrective work. No M3 implementation started.

## Delivered

- Read-only Codebeamer RESTv3 and Polarion RESTv1 adapters,3 synthetic projects per product, complete pagination, source-specific Project/Tracker/Type/field discovery and raw payload/relations/attachment retention.
- Source-discriminated credential-reference profiles; REST and CLI administration/configuration/preflight without the M5 wizard. Executable M2 OpenAPI snapshot, sanitized negative ACL tests and generated TypeScript client updated together; M1 snapshot preserved.
- Persistent server-wide rate/pause/credential/circuit policy and OS-held concurrent request slots; canonical origin/default ports share budgets. Header-first429/401 protection, bounded retries/bytes/deadline checks. All adapter requests, attachments and the explicitly verified mock renderer use the shared transport.
- COLLECT worker with heartbeat/fencing, complete raw and immutable latest-observed revisions, checksum-safe internal attachments, Item-local failure queue and continuation, conservative repeat scanning without duplicate revisions. Scope/missing/permission states stay distinct from deletion. Full SYNC and later stages remain409; active_revision_uid is not published in M2.

## Actual evidence

**PASS:** Main178 Python tests (14.50s), Frontend7 tests and TypeScript/Vite build, six-project API→HTTP MockTransport→Worker→SQLite/assets acceptance, static DOC_STATIC_PASS, package wheel/offline migrations1/2/3, runtime Python and Node audits0 known findings at scan time, local Linux-arm64 image Build/Boot and all3 services healthy. Network-disabled runtime smoke performed39 synthetic GET calls and verified duplicate-free repeat collection, attachments and live-network denial. Nonroot/proxy/migration settings observed. See TEST_REPORT.md.

**Independent QA:** full177 tests before the final minor regression, then1 targeted new invalid-port regression; all reported code findings resolved within local/mock scope. Three corrective review rounds are recorded in QA_REPORT.md. QA did not independently rerun Frontend/container checks; Main's actual results are distinguished.

**FAIL:** no unresolved known code failure at this checkpoint. Historical FAIL/Red outputs are preserved in QA_REPORT.md, TEST_REPORT.md and TDD records, not relabeled as passed.

## Required approval considerations

- **TDD_NOT_EVIDENCED:** initial connection/config profile prototype was written before its intended tests. Later API/CLI/normalization/correction tests have real Red→Green records, but cannot retroactively prove the initial order. This is a process exception requiring user review; TEST-058 is PARTIAL, not full PASS.
- **NOT VERIFIED:** actual ALM versions/permissions/TLS/production rate limits, renderer non-mutating behavior, processed HTML/display fidelity and real source deletion confirmation. Production renderer remains disabled. Generic deletion-evidence guard is tested, while adapters do not establish production deletion evidence; search exclusion/publication remains M4.
- Real socket hard interruption, non-macOS cross-process locking and shared/network filesystem coordination, Windows/native Linux/AMD64, image OS-layer security scan and remote GitHub CI remain NOT VERIFIED. Linux-arm64 basic offline runtime is observed; it is not a full platform matrix.
- Request totals are explicitly UNKNOWN with a mandatory-detail-call lower bound; unobserved attachment/page/retry costs are not represented as an exact estimate. Public failed-item-list/replay remains deferred under OI-029. Source profile auth/TLS catalogs require real-server evidence before use.
- Source-side changes between detail/relationship/attachment reads are not an immutable server snapshot. Hash/revision conflicts fail closed. Old noncanonical prototype server budgets require a separately reviewed stopped-worker state migration; no data is silently merged/deleted.
- Legacy REQ original clauses and OI-019/023 remain OPEN. No legacy clause was invented. Token chunking/model/index/search/full wizard are later milestones.

## Handoff

See M2_TRACEABILITY.csv (15 Primary+6 Shared), GATE_MATRIX.md (TEST-044..059), RUNBOOK.md and OPEN_ISSUES.md. Local test containers are stopped and their test volume retained; Colima cleanup status is recorded in TEST_REPORT.md. No actual ALM, remote Push, production deployment or Notion publication occurred.

Requested decision: review M2 local/mock results, retained external verification limits and the initial-profile TDD exception. Approve M2 before any M3 start. M2 is not implicitly approved by this report or its Git commit.
