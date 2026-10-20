# M1 — Foundation & Database

Status: APPROVED — user on 2026-10-20: “M1승인. 다음 단계를 진행해”. M2 start authorized; remote Push/deployment remain separately gated. See docs/milestones/M1/COMPLETION.md.

## Goal
공통 데이터 모델과 SQLite 마이그레이션, FastAPI CLI, 인증/Secrets, 영속 Worker Queue, Ollama/Qdrant 연결 스텁, Compose/Native 스켈레톤

## In-scope requirements
**Primary owner:** SRS-002, SRS-017, SRS-023, SRS-026, SRS-027, SRS-028, SRS-038, SRS-040, SRS-051, SRS-052, SRS-057

**Shared verification / cross-milestone:** SRS-001, SRS-019, SRS-025, SRS-039, SRS-041, SRS-042, SRS-043, SRS-044, SRS-056, SRS-058, SRS-059

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
실행가능 개발환경, 정규화 모델, 인증 API, Queue restart 테스트

## Deliverables
`docs/milestones/M1/PLAN.md`, `DESIGN.md`, `TEST_REPORT.md`, `QA_REPORT.md`, `COMPLETION.md`, plus related code/tests/ADR/API changes.

## External actions
ALM APIs strictly read-only; no Git remote push/deployment/credential export without separate approval and verified destination.

## v0.2 Requirements
Implement migration schema for server rate limit, failed item attempts, chunk budget configuration, backend/worker image and baseline CI. First create failing tests. Dockerfile is draft only until working source exists.

## v0.3 Baseline alignment — required handoff
- Primary SRS count: **11**; verify every Primary ID has implementation location and TEST-ID before requesting approval. Shared SRS must be checked at this gate as applicable; not silently dropped.
- File ownership / worktree and Main Agent merge boundaries must be recorded in `docs/milestones/M1/PLAN.md`. QA is independent and may not declare unrun tests as PASS.
- For each applicable SRS, provide Given/When/Then or equivalent executable acceptance test, actual command/result/log artifact and `TRACEABILITY.csv` status. No new Milestone before Human Approval.
- Foundation establishes authentication, data model, persistent jobs, rate/failure configuration, CLI/API scaffolding, lockfiles and Docker Boot Tests; **not** M2 discovery UI or M4 search indexes.
- API/Worker single-host SQLite policy: WAL/busy_timeout/writer serialization and crash-safe Job lock tests. Initialize `/healthz` and `/readyz` with no leak.
