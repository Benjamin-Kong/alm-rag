# M2 — ALM Collectors

Status: PLANNED — NOT STARTED

## Goal
CB/Polarion 커넥터/프로젝트 탐색/Tracker Type 선택/Revision/Fields/Relations/Attachments/수동 증분 동기화

## In-scope requirements
**Primary owner:** SRS-001, SRS-003, SRS-004, SRS-005, SRS-006, SRS-007, SRS-008, SRS-010, SRS-022, SRS-045, SRS-046, SRS-047, SRS-053, SRS-054, SRS-055

**Shared verification / cross-milestone:** SRS-039, SRS-041, SRS-044, SRS-049, SRS-058, SRS-059

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
Mock 양쪽 ALM 3개씩 + pagination/permission/attachment/revisions tests

## Deliverables
`docs/milestones/M2/PLAN.md`, `DESIGN.md`, `TEST_REPORT.md`, `QA_REPORT.md`, `COMPLETION.md`, plus related code/tests/ADR/API changes.

## External actions
ALM APIs strictly read-only; no Git remote push/deployment/credential export without separate approval and verified destination.

## v0.2 Requirements
Implement ALM-aware project registration; CB Tracker vs Polarion Work Item Type discovery; common rate limiter with Retry-After, per-source capability probes and fixture-driven tests.

## v0.3 Baseline alignment — required handoff
- Primary SRS count: **15**; verify every Primary ID has implementation location and TEST-ID before requesting approval. Shared SRS must be checked at this gate as applicable; not silently dropped.
- File ownership / worktree and Main Agent merge boundaries must be recorded in `docs/milestones/M2/PLAN.md`. QA is independent and may not declare unrun tests as PASS.
- For each applicable SRS, provide Given/When/Then or equivalent executable acceptance test, actual command/result/log artifact and `TRACEABILITY.csv` status. No new Milestone before Human Approval.
- Implement ALM projects/scopes via **CLI and REST** first. Do not require M5 React onboarding wizard for collector acceptance. M2 returns Project/Tracker vs Work Item Type catalogs and preflight; use mock response fixtures.
- ALM render POST is permitted only if proven non-mutating per version; prevent unbounded retries.
