# ALM RAG — Codex Development Package (Review Candidate v0.3)

## Status
**CONDITIONAL DOCUMENT BASELINE APPROVED (2026-10-19).** All 50 decisions and SRS-044~059 retained; REQ clause-level traceability is an OPEN ISSUE. Local Git preparation is permitted. M1 application implementation, real ALM tests and remote GitHub operations are NOT yet authorized/performed. See `docs/governance/BASELINE_APPROVAL.md`.

## Goal
Read-only fetch all selected Codebeamer Tracker Items and Polarion Work Items (fields, relationships, attachments), retain raw/HTML + immutable revisions in normalized SQLite schema, generate table-aware field-specific chunks, embed with Ollama EmbeddingGemma 2, and return authorized project-restricted distinct Item results from Vector+Keyword hybrid search via REST/CLI/Web UI.

## Entry points
1. `docs/requirements/DECISIONS.md` — final Q01–Q50 user choices.
2. `docs/requirements/SRS.md` — 59 traceable SRS requirements and acceptance criteria.
3. `docs/architecture/SAD.md`, `DATA_MODEL.md`, `INTERFACES.md` — architecture and contracts.
4. `docs/review/READINESS_REVIEW.md`, `OPEN_ISSUES.md` — pre-build validation and risks.
5. `plans/MASTER_PLAN.md`, `plans/M1_...md` through M6 — staged execution plans.
6. `AGENTS.md`, `.codex/config.toml`, `.codex/agents/*.toml`, `PROMPTS.md` — Codex policies and roles.
7. `docs/testing/TEST_PLAN.md` — non-fabricated quality evidence requirements.

## What to do now
- Read `docs/governance/BASELINE_APPROVAL.md` and `CODEX_PREFLIGHT.md` before starting.
- This package includes the **local Git initial commit**. For Private GitHub creation, see `docs/governance/GITHUB_SETUP.md`; no remote Push has occurred.
- Open this folder in Codex and use the **environment preflight** prompt in `PROMPTS.md`. Do not start M1 during preparation.
- Begin M1 only after an explicit new M1 start instruction, then enforce a separate Human Gate for each following milestone.

## Security
Do not put customer ALM raw text, screenshots, database exports, attachment contents, passwords or tokens into GitHub or Notion. `.gitignore` is defense in depth only; manually inspect staged changes and run secret scanning before any remote Push.

## References
- https://developer.siemens.com/polarion/rest-api-spec.html
- https://developer.siemens.com/polarion/latest/limitations-and-known-issues.html
- https://support.ptc.com/help/codebeamer/r3.1/en/codebeamer/developers_guide/swagger/26023354.html
- https://ollama.com/library/embeddinggemma-2
- https://qdrant.tech/documentation/search/hybrid-queries/
- https://developers.openai.com/cookbook/examples/codex/iterating-development-workflows-with-codex

## v0.2 상세 설계 검토 추가
User-requested 6 gaps are documented in: `docs/design/ALM_ONBOARDING.md`, `CHUNKING_POLICY.md`, `API_THROTTLING_AND_RETRY.md`, `FAIL_SAFE_AND_REPLAY.md`, `TDD_POLICY.md`, and `docs/architecture/DEPLOYMENT_AND_DEPENDENCIES.md`. Added SRS-044..059 and Test traceability. `deploy/` contains **non-runnable design skeletons** until M1 source/lockfiles are created. GitHub and M1 remain unstarted and approval gated.

## v0.3 Baseline review amendments
- All 50 Q decisions have decision-to-SRS rows in `docs/requirements/DECISION_COVERAGE.csv`. Legacy REQ-001~252 has a **best-effort** numeric mapping, with unresolved missing legacy text, in `docs/requirements/LEGACY_REQ_TRACEABILITY.csv`. This does not prove line-by-line equivalence to original legacy REQ clauses.
- 59 SRS entries explicitly assigned to M1~M6 in `docs/requirements/TRACEABILITY.csv` and plans.
- OpenAPI now includes a full draft endpoint inventory and security markers; per-endpoint schemas remain incomplete and must be locked in M1/M5.
- See `docs/review/BASELINE_AUDIT.md` before approving any implementation.
