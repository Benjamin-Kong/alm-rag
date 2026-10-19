# Codex Session Launch Prompts

## Pre-approval document review (allowed now)
Read `AGENTS.md`, `docs/requirements/DECISIONS.md`, `docs/requirements/SRS.md`, `docs/architecture/SAD.md`, `docs/review/READINESS_REVIEW.md`, `plans/MASTER_PLAN.md` and role configurations. Use independent subagents where helpful to: (1) find contradictory requirements, (2) assess item-level publication correctness and HTML table semantics, (3) verify practical testability and security. **Do not implement application code yet.** Produce a proposed change log and submit the final package to the user for approval.

## After explicit package approval: M1 only
The user has approved the SRS/SAD and beginning M1. Delegate M1 Foundation & Database to relevant specialist subagents. Create an implementation plan with file ownership/worktrees, implement only M1 scope, run actual tests, update SRS→Code→Test evidence, produce M1 Quality Gate report with PASS/FAIL/NOT VERIFIED and stop at M1 Human Gate. No M2 without further user approval. Do not Push remotely or export sensitive data without separately approved destination/policy.

## v0.3 Approval review prompt
Before M1, review docs/design/ALM_ONBOARDING.md, CHUNKING_POLICY.md, API_THROTTLING_AND_RETRY.md, FAIL_SAFE_AND_REPLAY.md, TDD_POLICY.md and docs/architecture/DEPLOYMENT_AND_DEPENDENCIES.md against SRS-044..059 and TEST-044..059. Treat numeric settings as DRAFT defaults, not hard limits; do not start M1 until user explicitly approves the package.

## Baseline Review v0.3 / No implementation
Read `docs/review/BASELINE_AUDIT.md`, `DECISION_COVERAGE.csv`, `LEGACY_REQ_TRACEABILITY.csv` and the six M1–M6 plans. Identify unresolved source-text gaps and API/schema assumptions; do not claim complete original REQ clause traceability. Do not create application source, GitHub repository, remote push or run M1 without user approval.


## v0.3 conditionally approved — Environment preflight ONLY (copy to Codex now)
The user has CONDITIONALLY APPROVED the ALM RAG v0.3 specification baseline on 2026-10-19, with unrecovered REQ-001..252 original clauses kept as OI-019 / OI-023. Read AGENTS.md, docs/governance/BASELINE_APPROVAL.md, docs/governance/CODEX_PREFLIGHT.md, docs/review/OPEN_ISSUES.md, and plans/MASTER_PLAN.md. Validate your installed Codex version/config, detect and list the six available specialist roles, check Git branch/clean state, run `python tools/validate_baseline.py`, and review M1 plan for execution readiness. Conduct DOCUMENT-ONLY role preflight and report PASS/FAIL/NOT VERIFIED with commands actually executed. DO NOT modify application code, launch M1, create GitHub remote resources, push, deploy, or access real ALM servers. Await a new explicit user instruction before M1 implementation.
