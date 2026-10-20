# M1 storage and queue evidence

Executed 2026-10-20 in isolated `.worktrees/m1-storage`, with synthetic temporary SQLite files only. Owned files: storage.py, queue.py, migrations/001_initial.sql, test_storage.py, test_queue.py and this document.

Command: `PYTHONPATH=src /Users/skongby/projects/alm-rag/.venv/bin/python -m pytest tests/test_storage.py tests/test_queue.py -q`.

- RED: initial test collection, exit 2, two ModuleNotFoundError errors (almrag.storage absent).
- GREEN: initial implementation, 5 passed in 0.30s.
- RED: validated generation missing evidence test, 1 failed / 6 passed in 0.29s. SQLite CHECK allows NULL unless explicitly excluded.
- GREEN: explicit non-null evidence constraint, plus rollback/token-bound/idempotency coverage, 8 passed in 0.28s.
- RED: INSERT OR REPLACE bypass of immutable revision delete trigger, 1 failed / 8 passed in 0.32s.
- GREEN: recursive triggers enabled on every application connection; final execution recorded in coordinator handoff.

SRS-002: deterministic UUID5 JSON components, unique source/project identity. SRS-023: revision ownership FK, immutable source, validated same-project active generations, transactional rollback. SRS-026: global FIFO partial unique RUNNING index, BEGIN IMMEDIATE writes, 3 independent processes race for one lease, restart/recovery checkpoint persistence, fencing. SRS-056: checkpoint foundation and failed item/attempt schema only; replay execution belongs to later milestones.

Queue returns dictionaries with JSON-decoded checkpoint. Direct SQLite rows contain checkpoint JSON text. `claim` returns `fencing_token`, used by checkpoint/heartbeat/finish. Expired/replaced tokens raise LeaseLost. `get_job` returns None when absent. `finish(..., error_code=None)` persists a bounded uppercase diagnostic code and appends job_events; no raw exceptions. PAUSED/BLOCKED never re-enter automatic claim. Expiry returns the original FIFO position to QUEUED; stage handlers must be idempotent before external effects exist.

Limitations: no live ALM/Qdrant/Ollama or actual publication/replay handler tested. Schema foundations do not establish end-to-end SRS completion. Per-stage throughput, authorization, container package inclusion and application integration require coordinator checks. SQL migrations must be included in the wheel/container. No milestone approval, remote push or commit performed by this agent.
