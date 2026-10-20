# M2 worker integration TDD evidence

Owner: collection specialist in isolated `.worktrees/m2-collection`. Date: 2026-10-20 Asia/Seoul. User approved remediation and continuation of M2. Only worker.py, test_m2_worker.py and this evidence file changed for this assignment; the previously delivered collection files remained frozen. No live ALM, network request, external publication or commit.

## Actual execution

Red command before worker implementation:

`PYTHONPATH=src /Users/skongby/projects/alm-rag/.venv/bin/python -m pytest -q tests/test_m2_worker.py`

Observed:9 FAILED in0.24s. Existing run_once accepted only(queue,owner); tests failed on the new service/heartbeat/health/stop injection arguments. This was the expected missing worker integration behavior; no skips/xfails were used.

Green with the minimum compatible integration:9 passed in0.58s.

Added actual CollectionService+SQLite integration for a long attachment request spanning original lease expiry and a stop request after a remote result. Executed targeted compatibility/integration regression:

`PYTHONPATH=src /Users/skongby/projects/alm-rag/.venv/bin/python -m pytest -q tests/test_m2_worker.py tests/test_runtime.py tests/test_foundation_integration.py`

Observed:17 passed in1.72s, one pre-existing upstream Starlette/httpx deprecation warning.

Full worktree regression:

`PYTHONPATH=src /Users/skongby/projects/alm-rag/.venv/bin/python -m pytest -q`

Observed:69 passed in6.38s, same upstream warning. `git diff --check` also passed.

## Behavior and traceability

| Requirement | Evidence |
| --- | --- |
| SRS-026 / TEST-026 | Claimed COLLECT jobs invoke the injected CollectionService. Service owns exactly one normal finish, preserving COMPLETED_WITH_ERRORS and other terminal states. Default calls without a service, empty queues and unsupported stages retain their M1 fail-closed behavior. |
| SRS-026/055 / TEST-026/055 | Dedicated heartbeat thread renews the same fencing token independently of slow connector calls. Interval is capped at the smaller of configured interval, lease/3 and10s. A request lasting beyond the original lease does not allow another owner to steal the job. Renewal parameters are finite and positive before claim. |
| SRS-055 / TEST-055 | Stop callback reaches service cancellation. LeaseLost or background heartbeat failure aborts the handler, propagates LeaseLost and performs no stale finish. A late source result after shutdown is not committed. Unexpected service errors become sanitized WORKER_ERROR/BLOCKED through Queue's guard. |
| SRS-057 / TEST-057 | Health file is written before collection and refreshed by the heartbeat thread during a long job; temporary file replacement prevents a partial health document. No raw exception/source bodies are logged. |
| SRS-058/059 / TEST-058/059 | Actual Red/Green execution, original worker compatibility, real SQLite+collection integration and full regression are recorded separately from unverified external behavior. |

The actual long-job integration completed2 references with1 successful immutable revision and1 isolated failure, with consistent counters and COMPLETED_WITH_ERRORS. The cancellation integration ended CANCELLED with zero revision/outcome writes.

## API and integration

`run_once(queue, owner, collection_service=None, *, stop_check=lambda:False, health_path=None, lease_seconds=30, heartbeat_interval=5)` returns whether a job was claimed. It does not interpret this Boolean as job success. The heartbeat thread always stops/joins on exit. CollectionService.run continues to own normal Queue.finish and lease-fenced data writes. Main catches LeaseLost in its loop and emits only a sanitized lease_lost event.

worker.main uses a lazy _ConfiguredCollection wrapper. For supported COLLECT jobs it constructs Connections(db,settings), passes connections.connector into CollectionService, and stores attachments below the configured database directory. Credentials/profiles are resolved only when a supported job runs. Main owns connection.py and the final ordered migration runner.

## NOT VERIFIED / limits

The isolated worktree lacks Main's connection.py and current startup settings, so the new lazy construction path must be tested after Main integrates it. Test injection verifies actual CollectionService.run but does not establish live server compatibility, production transport behavior, whole-process OS signals or container healthchecks. A synchronous connector call already in progress cannot be forcibly killed; its configured transport timeout bounds it, heartbeat continues, and cancellation/lease checks prevent later commits. The existing conservative unreferenced-attachment-file limitation remains documented in COLLECTION_TDD.md.
