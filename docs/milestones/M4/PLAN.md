# M4 hybrid retrieval and publication plan

2026-10-20. Status IN_PROGRESS; user “진행해” after M3 candidate4232f7a authorizes M4 on codex/m4-retrieval. M3 approved with documented limitations; real model/ALM remain NOT VERIFIED. No M5 implementation, remote Push, production deployment or live ALM/model. Static preflight DOC_STATIC_PASS42API; local SQLite3.50.4 FTS5 available.

Primary6: SRS-018/019/020/021/024/056. Shared9: SRS-008/022/023/039/041/049/055/058/059. No reassignment or recovered-legacy-clause invention.

Sequence: architecture/keyword ADR and frozen interfaces → actual SRS-linked failing tests → isolated implementations → Main integration/negative ACL/contract/client updates → unit/integration/mock E2E +actual dedicated synthetic local Qdrant/container tests where available → independent QA, max3bounded correction rounds with Critical/Major Human Gate → full evidence/traceability and approval STOP.

Ownership:
- Architect read-only contract review completed; no implementation edits.
- Vector specialist in .worktrees/m4-vector owns ONLY src/almrag/vector_store.py, tests/test_vector_store.py, docs/milestones/M4/VECTOR_TDD.md. Direct bounded HTTP Qdrant adapter with injected MockTransport; no runtime live calls by default.
- Lexical specialist in .worktrees/m4-lexical owns ONLY src/almrag/lexical.py, tests/test_lexical.py, docs/milestones/M4/LEXICAL_TDD.md. Frozen005keyword schema consumed; no shared migration edits.
- Main owns additive005migration, indexing/publication/readers/retrieval/orchestration/replay, M3 minimal stage reuse/refactor if tests require it, API/CLI/Worker/OpenAPI/typeclient, integration/real-local-Qdrant tests, docs/traces. All writes/activation fenced; QA read-only. No concurrent writers to same files.

Acceptance: no unauthorized project lookup in either channel; different project/generation pairs; staged/incomplete/new model results invisible; Item-unique top_k1..100; full/compact options; relations ID-only with target-scope validation; bounded overfetch/backfill; pinned read snapshot and live-reader protected cleanup; old active revision survives local-stage/vector/DB failure; deterministic points/restart/replay with no duplicates; complete-generation activation and delayed cleanup, no permanent rollback promise.

Known clarification: OI-029 GET failed-items is project_read in OpenAPI versus project_manage in FAIL_SAFE_AND_REPLAY. Main asked user early; independent retrieval/index work proceeds while that public route waits. Retry/resume routes already consistently require project_manage and will retain that policy. Production model/vector runtime remains explicit opt-in and fail-closed; local fixtures remain clearly synthetic.

## Bounded ownership updates

After the vector/lexical handoffs, Main delegated indexing.py/test_indexing.py/INDEX_TDD.md to the lexical worker in a new .worktrees/m4-index;005schema/readers/lexical were read-only seeds. After frozen18test handoff, Main owns integration changes including optional nonterminal stage execution (actualRed first). The vector specialist now owns only pipeline.py, additive006_pipeline.sql,test_pipeline.py,PIPELINE_TDD.md in a new .worktrees/m4-pipeline, consuming current Main dependencies read-only. Main retains all API/worker/runtime/retrieval and migration005 ownership. No conflicting writers.

## Latest checkpoint — HUMAN_REVIEW_REQUIRED

Independent QA confirmed Major OI-049 (SRS-018 exact Item ID retrieval missing). Implementation stopped under AGENTS.md on2026-10-20. See docs/milestones/M4/CORRECTION_PROPOSAL.md. Earlier IN_PROGRESS entries are historical. OI-029 resolved explicitly by user: list project_read, retry/resume project_manage. No completion/M5 approval.
