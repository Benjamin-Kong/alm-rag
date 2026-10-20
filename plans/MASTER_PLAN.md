# Master Execution Plan — Draft for Approval

**Gate:** v0.3 documentation was conditionally approved on 2026-10-19 for repository/Codex setup. **M1 implementation is NOT part of this preparation authorization** and requires an explicit subsequent M1 start instruction. Each Milestone has its own Human Gate.

**Current:** M1/M2 approved with retained limits; M3commit4232f7a approved with documented FIXTURE_ONLY/live/runtime limitations by subsequent user “진행해”. M4 IN_PROGRESS on codex/m4-retrieval; see docs/milestones/M4/PLAN.md. No M5, external Push, live ALM/model or production deployment is authorized.

## Milestones
| ID | Theme | Acceptance |
|---|---|---|
| M1 | Foundation & Database | 실행가능 개발환경, 정규화 모델, 인증 API, Queue restart 테스트 |
| M2 | ALM Collectors | Mock 양쪽 ALM 3개씩 + pagination/permission/attachment/revisions tests |
| M3 | Content Processing | 복잡 병합 표 fixture; 미변경 Chunk 0 임베딩; 모델 fingerprint test |
| M4 | Hybrid Retrieval | 프로젝트 누출 0; top_k item unique; stage crash & generations |
| M5 | Web UI & Operations | Playwright + 권한별 UI/Recovery/Export roundtrip |
| M6 | Integration & Quality | 실측 기록 + PASS/FAIL/NOT VERIFIED; 사용자 최종 승인 |

## Human gates and evidence
Each Milestone status is `PLANNED → IN_PROGRESS → QUALITY_REVIEW → PENDING_APPROVAL → APPROVED` or `BLOCKED/REJECTED`. No implicit approval.

## Execution priority
Run one Milestone at a time. Within each Milestone, parallelize independent tasks only. Worktrees must not modify same files concurrently.

## External source links
- Polarion official REST API: https://developer.siemens.com/polarion/rest-api-spec.html
- Polarion REST limitations: https://developer.siemens.com/polarion/latest/limitations-and-known-issues.html
- Codebeamer wiki2html: https://support.ptc.com/help/codebeamer/r3.1/en/codebeamer/developers_guide/swagger/26023354.html
- Ollama EmbeddingGemma 2: https://ollama.com/library/embeddinggemma-2
- Qdrant Hybrid Queries: https://qdrant.tech/documentation/search/hybrid-queries/
- Codex AGENTS.md and execution plans: https://developers.openai.com/cookbook/examples/codex/iterating-development-workflows-with-codex

## v0.2 Mandatory preflight and milestone gates
- **M1**: Define common auth/project profile model, failed-item table, persistent job state; create Python+React sources, dependency lock files, Docker build/boot, establish TDD evidence. API/Worker SQLite WAL with local volume, Qdrant remote/compose.
- **M2**: Codebeamer Project/Tracker and Polarion Project/Type discovery; shared HTTP rate-limit and 429 Retry-After; per-Item errors. Product-specific mocked contract tests first.
- **M3**: Chunk 512 target/1,024 max/64 overlap initial proposed; all-source coverage, Table JSON, tokenizer calibration and no silent truncation.
- **M4**: Replay from failed stage, staged atomic-ish publication + active revision validation, per-project filtered hybrid search.
- **M5**: Server/Project Wizard, rate-limit adjustments, Failed Item Explorer/retry/resume, actual Web UI Playwright, Notion reports.
- **M6**: Native/Docker cross-platform, TDD evidence audit, 429 load simulation, 15k-token Item, Item batch partial fail, worker-kill recovery, 100k Item benchmark.
- Human Gate applies after each milestone; v0.3 is conditionally approved for preparation only. M1 requires a separate explicit start instruction.

M4 latest checkpoint2026-10-20: HUMAN_REVIEW_REQUIRED, OI-049 Major exact Item ID retrieval gap. Implementation stopped pending approval of docs/milestones/M4/CORRECTION_PROPOSAL.md. M5 not authorized.

Latest authorization2026-10-21: user explicitly approved sequential M4→M5→M6 without additional human approval prompts. Quality/test/independent QA gates remain; correct failures before advancing. Earlier HUMAN_REVIEW_REQUIRED entry is historical: OI-049 correction authorized and IN_PROGRESS. External restrictions remain. See BASELINE_APPROVAL.md.
