# ALM RAG — Codex Main Coordinator Rules

## Mission
Build a read-only unified Codebeamer/Polarion ALM retrieval platform from the approved specifications in `docs/requirements/SRS.md` and `docs/architecture/SAD.md`. Do not extrapolate user intent beyond `docs/requirements/DECISIONS.md`.

## Stop condition: IMPORTANT
**The v0.3 document baseline was CONDITIONALLY APPROVED by the user on 2026-10-19. This approval authorizes Git/Codex environment preparation, NOT M1 implementation, remote GitHub creation or Push without access and separate approval. Do not implement application code or proceed to M1 until the user explicitly asks to start M1.** Read `docs/governance/BASELINE_APPROVAL.md`.

## Multi-Agent responsibility
Coordinator delegates to 6 specialist roles: requirements, architect, alm_collector, rag_engineer, frontend, qa. No need to spawn all agents every time. Parallelize independent bounded work only; ensure explicit file owner and worktree isolation. QA reviews independently and should not modify implementation code.

## Milestone discipline
- Follow `plans/MASTER_PLAN.md` sequentially M1..M6, one milestone at a time.
- Within a milestone, plan → design/ADR → implement → unit/integration/mock E2E → QA → up to 3 fix/retest iterations.
- On unresolved Critical/Major bugs, data loss, sensitive exposure, scope change to SRS/SAD, stop immediately and request human review.
- At completion create test evidence, QA report, open issues, doc/code traceability; request approval, then STOP until approved.
- Record PASS/FAIL/NOT VERIFIED separately; never claim unrun tests passed.

## Security and external actions
- ALM source strictly read-only. Server-side Wiki renderer POST can be used only after confirming it does not modify ALM content.
- Never add actual ALM dumps, attachments, customer text, tokens, passwords, SQLite/Qdrant files, private keys or raw production logs to GitHub/Notion.
- Require separate explicit approval for: Git remote push, deployment, destructive DB operations, unexpected network transmissions, changes to authentication/ACL.
- Use environment variables/OS secure secret store, sanitized fixtures, least privilege and fail-closed authorization.

## Source of truth and documentation
Git is source-of-truth for SRS/SAD/SDD/ADR/API/tests; Notion is a summary/approval index only. Notion root page: https://app.notion.com/p/3fe8be2feeee81d4ad48cddc61ba0f5c . Actual automatic publishing is *not* implemented: do not mark it completed until implemented and tested.

## Preflight
Verify project Codex version/config support before relying on multi-agent roles. Validate TOML and AGENTS.md. If changed Codex settings deprecate a key, update configurations with docs evidence and report it. Use `docs/review/OPEN_ISSUES.md` to flag assumptions.

## v0.2 구체 추가 개발 규칙
- Every new behavioral feature/bug fix: Write and run a failing SRS-linked test first (Red), implement minimum fix (Green), refactor and run regression tests. Record real evidence, do not fabricate test executions. `docs/design/TDD_POLICY.md`.
- Register ALM instances via `source_type` discriminated forms, discover Project/Tracker vs Work Item Type separately. `docs/design/ALM_ONBOARDING.md`.
- Never enforce one Item = one Chunk. Token-bound chunks with complete original Item in SQLite. No silent truncation. `docs/design/CHUNKING_POLICY.md`.
- Every connector HTTP call including attachments/wiki rendering must pass shared server rate-limit transport; 429 Retry-After and global pause are mandatory. `docs/design/API_THROTTLING_AND_RETRY.md`.
- Continue after isolated per-Item failures; keep failed-item queue and replay; stop globally on integrity/credentials/security/circuit-open. `docs/design/FAIL_SAFE_AND_REPLAY.md`.
- Deployment artifacts in `deploy/` are **DRAFT skeleton only** until source, lock files and CI Build/Boot are implemented in M1. No false claim of Docker test PASS.
- QA must verify TEST-044..059 and refer to v0.2 review; follow all Q01~Q50 immutable decisions unless user re-approves change.

## v0.3 static baseline gate
- At preflight run `python tools/validate_baseline.py`; static PASS is evidence of spec files only, **never** application test success.
- Read `docs/review/BASELINE_AUDIT.md` and `docs/requirements/DECISION_COVERAGE.csv`. Legacy REQ coverage is decision-level; do NOT invent unrecovered original REQ clauses.
- Use Primary / Shared milestone assignments in `docs/requirements/TRACEABILITY.csv`, not old in-scope lists or the stale README text.
- A proposed API endpoint does not count as implemented. Update OpenAPI, negative ACL/security tests, type-safe client and docs together when changing an API.
- M1 must not require M5 React wizard; M2 project/scope discovery must be testable without UI.
- If user approves baseline, that does NOT override the separate approval requirement for remote GitHub Push, deployment, remote Notion transmission of confidential content, or dangerous operations.
