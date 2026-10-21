# ALM RAG — Codex Development Package (Review Candidate v0.3)

## Status
M1–M6 locally implemented and quality verified with documented limitations (2026-10-21). Independent **506 Python /28 frontend PASS**, root **10 Chromium PASS**, local Docker/isolated wheel/audits PASS. Synthetic100kItem/199999Chunk exact-ID search P95 **1.37495s**; this is not actual-Ollama/semantic-performance evidence. Actual ALM/model/production100k pipeline/other host modes/remote CI remain NOT VERIFIED. See [M6 completion](docs/milestones/M6/COMPLETION.md), [test report](docs/milestones/M6/TEST_REPORT.md), [benchmark interpretation](docs/milestones/M6/BENCHMARK_REPORT.md) and [runbook](docs/milestones/M6/RUNBOOK.md).

## 실행 방법

처음 실행할 때는 [한국어 실행 안내](docs/GETTING_STARTED.ko.md)를 참고하세요. 설치, 임시 HTTPS 데모, 데이터가 보존되는 Compose/Native 실행, 최초 관리자 생성과 HTTPS 조건을 설명합니다.

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

- Read the latest milestone TEST_REPORT/QA_REPORT/GATE_MATRIX and TRACEABILITY records; static baseline validation alone does not establish application success.
- Use M6/RUNBOOK.md for current Native/Compose, quality APIs/CLI and frontend validation. Original/normalized SQLite, staged hybrid search, durable replay, source-specific admin wizard, ZIP operations and isolated raw-only recovery are implemented.
- Supply actual model/tokenizer and authorized read-only ALM access only in a separate explicitly authorized integration exercise; default live flags stay false. No remote Push/Notion publication or production deployment was performed.

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
User-requested 6 gaps are documented in: `docs/design/ALM_ONBOARDING.md`, `CHUNKING_POLICY.md`, `API_THROTTLING_AND_RETRY.md`, `FAIL_SAFE_AND_REPLAY.md`, `TDD_POLICY.md`, and `docs/architecture/DEPLOYMENT_AND_DEPENDENCIES.md`. Added SRS-044..059 and Test traceability. The historical Docker skeletons have been replaced by locally tested M1 foundation images and lockfiles; full collection/search/operations remain later milestones.

## v0.3 Baseline review amendments
- All 50 Q decisions have decision-to-SRS rows in `docs/requirements/DECISION_COVERAGE.csv`. Legacy REQ-001~252 has a **best-effort** numeric mapping, with unresolved missing legacy text, in `docs/requirements/LEGACY_REQ_TRACEABILITY.csv`. This does not prove line-by-line equivalence to original legacy REQ clauses.
- 59 SRS entries explicitly assigned to M1~M6 in `docs/requirements/TRACEABILITY.csv` and plans.
- OpenAPI now includes a full draft endpoint inventory and security markers; per-endpoint schemas remain incomplete and must be locked in M1/M5.
- See `docs/review/BASELINE_AUDIT.md` before approving any implementation.

현재2026-10-21: M4 로컬 품질 검증 완료(417 Python 테스트,10 frontend 테스트,합성 실제Qdrant/패키지/컨테이너). [M4 보고서](docs/milestones/M4/COMPLETION.md). 사용자 명시 승인에 따라 M5→M6를 추가 승인 없이 순차 진행한다. 실ALM/모델·원격Push/Notion·운영배포 제한과 NOT VERIFIED 항목은 유지한다.


M5 local quality candidate (2026-10-21): source-specific React wizard, jobs/diagnostics/search/original Explorer, durable ZIP Export/Import, raw-only isolated recovery, disabled-by-default summary publisher. Evidence: [M5 test report](docs/milestones/M5/TEST_REPORT.md), [runbook](docs/milestones/M5/RUNBOOK.md). Actual ALM/model/Notion/production deployment remain NOT VERIFIED. User has authorized M6 continuation without another milestone prompt.

M6 latest evidence supersedes earlier appended checkpoint statuses. No further milestone implementation is pending in the authorized sequence; separately authorized real-environment validation remains necessary before production claims.
