# M2 shared transport — authorized repair evidence

Date: 2026-10-20. Requirements: SRS-053/054. User authorized OI-035/036/037 repairs with “수정안을 적용하고 계속진행해”. Work performed only in `.worktrees/m2-transport`; no live sockets, ALM access, commits, Push or deployment. Implementation owner changed only `src/almrag/alm_http.py`, `tests/test_alm_http.py` and this file. Seeded storage/migration files were not changed.

## Actual Red → Green

All pytest commands used `PYTHONPATH=src /Users/skongby/projects/alm-rag/.venv/bin/python -m pytest ...` from the isolated worktree, so they exercised its module rather than Main's installed editable package.

1. Added protection-header/body-limit/permit-release ordering, empty-response/deadline acquisition, long-stream permit and nonfinite Retry-After regressions before implementation changes. `tests/test_alm_http.py -q`: **4 failed, 9 passed in 0.75s**, exit1. Oversized429 had persisted pause0; empty200 succeeded late; another request reclaimed an active permit; NaN removed backoff. After minimum implementation: **13 passed in0.63s**, exit0.
2. Added separate spawned-process active-stream and crash-recovery tests, stream-abort cleanup and persisted policy reduction checks: **17 passed in1.20s**. The initial separate-process counterexample mistakenly retained timeout30 and passed on the old code; this was not accepted as Red evidence. Corrected its child timeout to1. Temporarily restored Main's original transport in this isolated worktree, ran the single corrected process test, then restored the repaired file in `finally`: **1 failed,16 deselected in0.55s**, exit1. Old code sent the competing request while the expired owner's stream remained open. Repaired transport plus migration regression: **18 passed in1.33s**, exit0.
3. Canonical DB-path alias refinement: new symlink-alias test first **1 failed,17 deselected in0.20s**, exit1; canonicalized both parent and filename before selecting stable slot files. Full regression then **57 passed,1 warning in4.75s**, exit0.
4. Reservation rollback refinement: new synthetic SQLite commit failure regression first **1 failed,18 deselected in0.22s**, exit1, because the uncommitted reservation retained an OS lock. Added rollback cleanup; transport tests **19 passed in1.26s**, exit0.

A mistyped intermediate regression command named nonexistent `tests/test_storage_queue.py`; pytest exited4 with no tests run. This is not counted as verification. Corrected actual full regression results are recorded below.

## Corrected behavior

- Classify401 and retryable429/5xx status/headers before reading bodies. Persist credential block/global pause while the permit is still owned; discard error bodies. Oversized or sensitive error bodies cannot bypass protection or appear in exceptions.
- Keep stable OS advisory slot files next to the canonical SQLite database. SQLite permits encode slot identity; expired rows can be reclaimed only when the corresponding OS lock is available. Active blocked streams retain ownership after their SQLite expiry; process death releases OS ownership, and expiry recovers the stale row. Never unlink/recreate slot files. Count active permits against the persisted server policy across clients/processes. No network or sleeps under SQLite transactions.
- Validate total deadline before acquisition/send, at headers, each yielded chunk, empty body completion, stream/client close and return. Abort closes streams and releases permits. Invalid nonfinite Retry-After uses configured backoff.
- Existing live-network default-deny, read-only method/path restrictions, bounded bytes, retry/circuit and shared pacing remain exercised.

## Final local acceptance and limits

Final isolated regression: **58 passed,1 warning in4.73s**, exit0 (19 transport,1 M2 migration,38 M1 tests). Starlette emits its existing httpx TestClient deprecation warning; no test was skipped. Spawned-process tests used synthetic HTTPX streams and a temporary SQLite file on local macOS. No actual ALM network traffic occurred.

**NOT VERIFIED:** Linux/Windows OS-lock branches, network-mounted SQLite/locks, real server/socket timing and live version compatibility. POSIX uses `flock`; Windows uses `msvcrt.locking`. All processes must share the canonical SQLite parent/slot files on a filesystem that supports these locks; private copies of that directory do not provide distributed coordination. Stop pre-M2 prototype workers before upgrading their UUID-only permits. Do not delete slot files while workers run. A synchronous HTTP operation can return control after the logical total deadline while blocked; this implementation rejects late completion and retains the concurrency permit throughout, but does not claim a hard wall-clock socket interruption beyond HTTPX phase timeouts. Custom transports can ignore timeouts, as the regression deliberately does.

Frozen for Main integration and independent QA. This report does not accept the new unrelated connector Major or claim M2 completion.
