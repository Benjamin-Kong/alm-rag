# M4 — Hybrid Retrieval

Status: IN_PROGRESS — user “진행해” after M3commit4232f7a authorizes M4. See docs/milestones/M4/PLAN.md and DESIGN.md.

## Goal
Qdrant dense/키워드 BM25/프로젝트 필터/RRF/Item 복원/게시/Index generation

## In-scope requirements
**Primary owner:** SRS-018, SRS-019, SRS-020, SRS-021, SRS-024, SRS-056

**Shared verification / cross-milestone:** SRS-008, SRS-022, SRS-023, SRS-039, SRS-041, SRS-049, SRS-055, SRS-058, SRS-059

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
프로젝트 누출 0; top_k item unique; stage crash & generations

## Deliverables
`docs/milestones/M4/PLAN.md`, `DESIGN.md`, `TEST_REPORT.md`, `QA_REPORT.md`, `COMPLETION.md`, plus related code/tests/ADR/API changes.

## External actions
ALM APIs strictly read-only; no Git remote push/deployment/credential export without separate approval and verified destination.

## v0.2 Requirements
Ensure old active Item on failed Item staging and idempotent Item replay from failed Stage; IndexPoint duplicate 0 after retry.

## v0.3 Baseline alignment — required handoff
- Primary SRS count: **6**; verify every Primary ID has implementation location and TEST-ID before requesting approval. Shared SRS must be checked at this gate as applicable; not silently dropped.
- File ownership / worktree and Main Agent merge boundaries must be recorded in `docs/milestones/M4/PLAN.md`. QA is independent and may not declare unrun tests as PASS.
- For each applicable SRS, provide Given/When/Then or equivalent executable acceptance test, actual command/result/log artifact and `TRACEABILITY.csv` status. No new Milestone before Human Approval.
- Mandatory revision visibility + overfetch/backfill + project/generation multi-project consistency tests. Search must not expose staged/new chunks before activation.
- Resolve keyword engine by ADR with Korean and automotive SW token fixture.

## Latest checkpoint — HUMAN_REVIEW_REQUIRED

Independent QA confirmed Major OI-049 (SRS-018 exact Item ID retrieval missing). Implementation stopped under AGENTS.md on2026-10-20. See docs/milestones/M4/CORRECTION_PROPOSAL.md. Earlier IN_PROGRESS entries are historical. OI-029 resolved explicitly by user: list project_read, retry/resume project_manage. No completion/M5 approval.

Final2026-10-21: LOCAL_QUALITY_VERIFIED_WITH_DOCUMENTED_LIMITATIONS. Independent417PASS64.63s, OI-049resolved, certifi advisoryfixed/reaudit0, finalpackaging/container/clientgatesPASS. Userexplicitlyauthorized M5/M6 continuation without furtherHumanprompts; see M4/COMPLETION.md. Earlierstopentrieshistorical.
