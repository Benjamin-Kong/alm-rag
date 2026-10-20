# M3 — Content Processing

Status: APPROVED_WITH_DOCUMENTED_LIMITATIONS — user “진행해” after commit4232f7a delivery. M4 separately authorized; original M3 evidence and actual-model/ALM limitations retained.

## Goal
HTML DOM·Table JSON·Fallback·Field-aware Chunk·Hash·선택적 임베딩

## In-scope requirements
**Primary owner:** SRS-009, SRS-011, SRS-012, SRS-013, SRS-014, SRS-015, SRS-016, SRS-048, SRS-049, SRS-050

**Shared verification / cross-milestone:** SRS-010, SRS-017, SRS-039, SRS-041, SRS-055, SRS-058, SRS-059

## Assigned agents
Main Coordinator delegates requirements/architecture/ALM Collector/RAG Engineer/Frontend/QA according to stage, never forcing all six to run concurrently.

## Execution protocol
1. Read SRS, SAD, module contracts and existing code. Define task ownership and Worktree boundaries.
2. Design interfaces and data migrations before implementation. Record decisions in ADR/SDD.
3. Have implementation specialists edit independent files in their own worktree only when parallelism is beneficial.
4. Integrate via Main Agent; independently run QA and applicable unit/integration/mock E2E tests.
5. For failure, allow up to 3 repair+revalidation cycles; escalate critical security/ALM destructive risk immediately.
6. Update traceability and report observed PASS/FAIL/NOT VERIFIED; prepare Notion-safe summary and Git diff/commit references.
7. STOP at user approval gate. Never start the next milestone without explicit approval.

## Acceptance criteria
복잡 병합 표 fixture; 미변경 Chunk 0 임베딩; 모델 fingerprint test

## Deliverables
`docs/milestones/M3/PLAN.md`, `DESIGN.md`, `TEST_REPORT.md`, `QA_REPORT.md`, `COMPLETION.md`, plus related code/tests/ADR/API changes.

## External actions
ALM APIs strictly read-only; no Git remote push/deployment/credential export without separate approval and verified destination.

## v0.2 Requirements
Implement token-budget chunking, full source-span validation and table header-row repeat; test oversized 15k token Item and oversized table row.

## v0.3 Baseline alignment — required handoff
- Primary SRS count: **10**; verify every Primary ID has implementation location and TEST-ID before requesting approval. Shared SRS must be checked at this gate as applicable; not silently dropped.
- File ownership / worktree and Main Agent merge boundaries must be recorded in `docs/milestones/M3/PLAN.md`. QA is independent and may not declare unrun tests as PASS.
- For each applicable SRS, provide Given/When/Then or equivalent executable acceptance test, actual command/result/log artifact and `TRACEABILITY.csv` status. No new Milestone before Human Approval.
- Do not equate Item contents with one chunk: entire original Item from SQLite, bounded token-budget chunks in Qdrant, no silent truncation.
