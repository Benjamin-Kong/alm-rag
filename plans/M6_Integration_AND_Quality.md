# M6 — Integration & Quality

Status: PLANNED — NOT STARTED

## Goal
10만 Item 검증, 골든셋 평가, End-to-End, OS cross-platform, P95 Benchmark

## In-scope requirements
**Primary owner:** SRS-033, SRS-034, SRS-035, SRS-036, SRS-037, SRS-039, SRS-041, SRS-043, SRS-058, SRS-059

**Shared verification / cross-milestone:** SRS-038, SRS-051, SRS-052

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
실측 기록 + PASS/FAIL/NOT VERIFIED; 사용자 최종 승인

## Deliverables
`docs/milestones/M6/PLAN.md`, `DESIGN.md`, `TEST_REPORT.md`, `QA_REPORT.md`, `COMPLETION.md`, plus related code/tests/ADR/API changes.

## External actions
ALM APIs strictly read-only; no Git remote push/deployment/credential export without separate approval and verified destination.

## v0.2 Requirements
Validate Docker build and three host OS modes, TDD Red/Green evidence, Model context calibration, simulated 429/401/403 and batch fail-safe. Report actual vs mock NOT VERIFIED.

## v0.3 Baseline alignment — required handoff
- Primary SRS count: **10**; verify every Primary ID has implementation location and TEST-ID before requesting approval. Shared SRS must be checked at this gate as applicable; not silently dropped.
- File ownership / worktree and Main Agent merge boundaries must be recorded in `docs/milestones/M6/PLAN.md`. QA is independent and may not declare unrun tests as PASS.
- For each applicable SRS, provide Given/When/Then or equivalent executable acceptance test, actual command/result/log artifact and `TRACEABILITY.csv` status. No new Milestone before Human Approval.
- Do not block acceptance due to unavailable real ALM unless required by current approved policy (Q40 B, mock E2E required). Record real integration as NOT VERIFIED rather than PASS.
