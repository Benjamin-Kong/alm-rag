# M4 Pipeline API / CLI TDD evidence

Scope: SRS-023/024/025/026/049/055/056; OI-029 user decision permits failure listing with project_read. Retry and resume retain project_manage.

Tests executed with `PYTHONPATH=.worktrees/m4-api/src .venv/bin/pytest` against the isolated source and sanitized fixtures only.

- Red: new pipeline preflight/SYNC dispatch, failure list and replay ACL, sanitized errors and CLI commands were absent. `tests/test_m4_api.py tests/test_m4_worker_cli.py`: **4 failed, 7 passed in 2.10s**.
- Intermediate Red after API/CLI implementation: **1 failed, 10 passed in 2.28s**. Audit sanitizer omitted the three new operator action names; no credential or permission behavior changed to address this.
- Green/regression: `test_m4_api.py test_m4_worker_cli.py test_security.py test_m2_api.py test_m3_api.py`: **26 passed in 5.17s**. `git diff --check` passed for owned implementation/test files.
- A mistyped optional regression path (`test_processing_api.py`, nonexistent) produced no tests run; it was corrected to `test_m3_api.py` in the recorded successful invocation.

The routes expose typed pipeline preflight, SYNC enqueue and alias, failed item listing, individual/all replay and resume. Tests verify read-only listing, manage-only mutations, unknown/foreign job non-disclosure and authorization before service calls, request limits, sanitized conflict responses, percent-encoded CLI paths and successful operation audit using a hashed actor reference plus project/job identifiers. Raw API keys and source Item identifiers are excluded from these audit events.

No actual ALM, model server, remote publishing, or deployment was performed. Whole-suite, generated-client and real Qdrant verification belong to coordinator integration and are not claimed here.
