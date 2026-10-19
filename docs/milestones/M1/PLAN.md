# M1 Foundation & Database

Status: IN_PROGRESS. User instruction on 2026-10-19: “커밋반영하고 착수해”. This explicitly authorizes M1; no remote Push, deployment, live ALM access or M2 start is authorized.

Environment preparation commit: `a4dbaa6`. Branch: `codex/m1-foundation`.

## Scope and sequence

Primary: SRS-002/017/023/026/027/028/038/040/051/052/057. Shared gates: SRS-001/019/025/039/041/042/043/044/056/058/059. TRACEABILITY.csv remains the assignment authority.

1. Design storage/auth/queue contracts; write SRS-linked tests and record their actual failures.
2. Implement minimum normalized schema, migration, persistent FIFO/lease/checkpoint, configuration, encrypted secrets/audit, auth API, CLI and independent worker.
3. Add React/TypeScript foundation and typed API client, locked Native/container install and CI.
4. Execute unit/integration/mock acceptance and native/container smoke; independent QA, at most three fix/retest rounds.
5. Record partial and unverified cross-milestone requirements; request M1 Human Approval only after applicable gates pass. Never start M2 implicitly.

## Ownership and isolation

- Main: package/lock, config, auth/API/CLI, API contract, integration, Docker/CI, governance and evidence.
- RAG specialist: isolated managed Worktree for `src/almrag/storage.py`, `src/almrag/queue.py`, `src/almrag/migrations/`, `tests/test_storage.py`, `tests/test_queue.py`, storage TDD evidence only. No shared-file edits; Main integrates explicitly.
- Frontend specialist: isolated managed Worktree for `frontend/` only plus frontend TDD evidence. No M5 wizard; minimal status surface and typed client.
- Requirements/Architect: read-only contract and scope review, no implementation files.
- QA: read-only independent review; no production code edits.

Worktree paths and exact handoffs are recorded when created. No concurrently edited file is shared across writers. Git is source of truth; no automatic Notion publishing claim.

## Deferred behaviors

Real ALM discovery/collectors M2; content/model inference M3; index publication/search and replay integration M4; full operations UI M5; cross-platform/performance matrix M6. Public unimplemented stages must fail closed, never return fabricated success. M1 exercises queue recovery using synthetic injected handlers and synthetic fixtures only.
