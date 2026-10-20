# M4 SYNC / internal replay TDD evidence

Date: 2026-10-20. Owner: rag_engineer, isolated `.worktrees/m4-pipeline`.
Owned files: `src/almrag/pipeline.py`, additive `006_pipeline.sql`, `tests/test_pipeline.py`, this document. Root-owned 005/indexing/collection/readers/lexical/vector modules were copied as read-only dependencies; no root API/settings/auth/migration edits were made here.

## Scope and requirements

SRS-023/025/026/049/055/056: one global FIFO parent job drives COLLECT → PROCESS → EMBED → INDEX, with a pinned collection catalog/config and processing policy/runtime identity. Collection and index run with `finish=False`; only the pipeline finishes its parent. Processing private per-Item operations share the parent fence, using separate stage checkpoints to avoid M3's single-stage outcome-key collision.

The additive tables retain immutable pipeline and post-collection processing snapshots, PROCESS/EMBED outcomes, replay identity and original failure reference. No original revision or active pointer is rewritten by orchestration. IndexService alone validates and publishes. Same-config INDEX can publish ready siblings while local failures retain old active revisions; changed-config REBUILD keeps complete expected coverage and refuses a partial replacement. Storage/model/auth/integrity errors stop globally. Lost fences propagate; runtime callbacks are restored even during crash unwinding.

Internal `list_failures` merges actual `failed_items` and source collection failures without inventing a revision. `retry` accepts an existing Item UID, or a source Item identifier when collection failed before an Item existed; it pins expected revision, scope and current effective processing identity. Its idempotency key is original job / source Item / starting stage / original revision / effective config. A retry queued for the same key returns the same job, preserving FIFO. Successful replay resolves only its referenced original failure. Retrying a terminal replay's new failure uses that replay job's own failure record.

Only COLLECT / explicit force_recollect accesses a connector during replay. That path validates the selected source ref and uses root's targeted-replay guard, retaining sibling memberships. A recollection may create a newer actual revision; after a checkpoint, crash recovery validates that new pin, rather than confusing it with the original failure revision that authorized recollection. No-recollect paths use local preserved revisions only.

`resume` only requeues PAUSED/BLOCKED retained-snapshot jobs for enumerated recoverable error codes and revalidates current runtime/config/scope first. Structural integrity errors and successful/cancelled/failed jobs are not silently resumed. The same method supports retained standalone COLLECT, PROCESS, EMBED, INDEX and REBUILD snapshots. No public failed-list authorization is inferred; OI-029 remains a coordinator/user policy question.

## Actual Red / Green executions

Commands ran from the isolated worktree, using `/Users/skongby/projects/alm-rag/.venv/bin/python`.

1. `... -m pytest -q tests/test_pipeline.py`: exit 2, `ModuleNotFoundError: almrag.pipeline` before implementation.
2. Added constructor/method behavior stub; same command: exit 1, **9 failed** (0.35 s), all `NotImplementedError`.
3. Implemented orchestration and migration; same command: exit 1, **1 failed, 8 passed** (9.83 s). The failed test incorrectly expected INDEX records in the PROCESS/EMBED-only table. Corrected it to four processing checkpoints plus two real `index_outcomes`; the implementation was not altered to mirror the erroneous assertion.
4. Added post-recollection crash and checkpointed-scope recovery cases; same command: exit 1, **2 failed, 11 passed** (10.58 s). Reproduced incorrect comparison against original revision after explicit recollection, and missing scope validation when resuming an already checkpointed SYNC.
5. Added minimal checkpoint-pin validation on replay/recovery/resume; same command: exit 0, **13 passed** (10.63 s).
6. Added current-selection exclusion before the next collection. `... -m pytest -q tests/test_pipeline.py -k newly_excluded`: exit 1, **1 failed, 13 deselected** (0.57 s). Stale IN_SCOPE membership alone admitted a tracker newly excluded in local project selection. Added current project selection validation to replay/pin checks; full target command: exit 0, **14 passed** (10.95 s).
7. Added paginated failure lookup case. `... -m pytest -q tests/test_pipeline.py -k beyond_first_page`: exit 1, **1 failed, 14 deselected** (0.36 s), because retry searched only the first 1,000 failures. Added page-wise lookup retaining bounded page memory; final full regression below includes all 15 cases.

The 15 cases use real SQLite migrations, CollectionService, ProcessingService, IndexService and a synthetic source adapter / MemoryVector. One pagination boundary case injects synthetic failure pages. They cover:

- One parent / one terminal event, exact aggregate counts, unchanged repeat with zero new content embedding calls.
- 100 Items, three local EMBED failures → 97 publications, then three replay jobs → 100, no duplicate points and no source detail calls in EMBED replay.
- Collection failures with no revision, and targeted recollection retaining sibling memberships.
- Replay idempotency, expected revision, current scope, model identity drift.
- Global auth stops before embedding; incomplete new-model generation cannot switch the old generation.
- Crash after durable PROCESS, expired lease rejection, reclaim/recovery, model pause/resume, config/scope drift rejection and runtime callback restoration.

## Regression observations

Initial full `... -m pytest -q`: exit 1, **1 failed, 318 passed** (47.95 s). The inherited native-worker test started a subprocess without PYTHONPATH, so the shared environment's editable installation imported the concurrently changed root worker rather than this isolated checkout. That old test expected M3 `STAGE_UNAVAILABLE` for SYNC. No pipeline test failed. A subsequent full run explicitly pins `PYTHONPATH` to this worktree's `src`; its result is recorded below.

`env PYTHONPATH=/Users/skongby/projects/alm-rag/.worktrees/m4-pipeline/src ... -m pytest -q`: exit 0, **319 passed** (47.99 s), before the two additional boundary cases. Final full regression after both fixes is recorded below.

Final same full command: exit 0, **321 passed in 47.95 s**, including all 15 pipeline cases. No files changed during this final run. Final `git diff --check` and project-Python static baseline were repeated successfully.

Project Python `tools/validate_baseline.py`: exit 0, **DOC_STATIC_PASS**, 50 decisions / 252 legacy mappings / 59 SRS / 6 subagents / 42 draft API operations. This is static document evidence only. `git diff --check`: exit 0.

## Limits

**NOT VERIFIED:** actual ALM/model/Qdrant servers, production network interruption, root API/CLI/Worker integration, standalone-stage resume against real runtimes and multi-platform process crashes. No actual server, model download, remote push, deployment or destructive production action occurred. Real source content and secrets were not used. Independent integrated QA remains a coordinator responsibility.
