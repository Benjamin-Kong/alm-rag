# M5 — Web UI & Operations

Status: PLANNED — NOT STARTED

## Goal
React 대시보드·Explorer·관리 API·로그/감사·백업/복구·Export/Import

## In-scope requirements
**Primary owner:** SRS-025, SRS-029, SRS-030, SRS-031, SRS-032, SRS-042, SRS-044

**Shared verification / cross-milestone:** SRS-003, SRS-026, SRS-027, SRS-028, SRS-039, SRS-040, SRS-041, SRS-045, SRS-046, SRS-047, SRS-053, SRS-056, SRS-057, SRS-058, SRS-059

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
Playwright + 권한별 UI/Recovery/Export roundtrip

## Deliverables
`docs/milestones/M5/PLAN.md`, `DESIGN.md`, `TEST_REPORT.md`, `QA_REPORT.md`, `COMPLETION.md`, plus related code/tests/ADR/API changes.

## External actions
ALM APIs strictly read-only; no Git remote push/deployment/credential export without separate approval and verified destination.

## v0.2 Requirements
Add wizard, scope preview, API rate-control settings, Failed Item explorer/retry/resume and per Item trace log; Playwright mock E2E.

## v0.3 Baseline alignment — required handoff
- Primary SRS count: **7**; verify every Primary ID has implementation location and TEST-ID before requesting approval. Shared SRS must be checked at this gate as applicable; not silently dropped.
- File ownership / worktree and Main Agent merge boundaries must be recorded in `docs/milestones/M5/PLAN.md`. QA is independent and may not declare unrun tests as PASS.
- For each applicable SRS, provide Given/When/Then or equivalent executable acceptance test, actual command/result/log artifact and `TRACEABILITY.csv` status. No new Milestone before Human Approval.
- React wizard belongs to M5; earlier M2 project/scope APIs are dependency and must remain stable. Backup/Import/Export use sensitive-data exclusions and consistent manifests.
- Include real UI E2E mocked backend and source HTML XSS sanitization tests.
