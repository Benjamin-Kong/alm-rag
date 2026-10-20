# M2 final local test report — 2026-10-20

Latest executable checks PASS as scoped below; milestone approval is pending. Original failed/partial observations follow as history. Synthetic fixtures only; no actual ALM access.

| Assessment | Actual command/scope | Result |
|---|---|---|
| PASS | `.venv/bin/python -m pytest -q` |178 passed,1 existing Starlette/httpx deprecation warning,14.50s,exit0; no skip/xfail |
| PASS | `npm --prefix frontend test` with Node22 PATH |7 passed,exit0 |
| PASS | `npm --prefix frontend run build` | TypeScript+Vite built,exit0 |
| PASS | `tests/test_m2_mock_e2e.py` |6 passed in4.38s;3 projects per product, HTTP mocks/API/Worker/SQLite/assets and repeat scans; included in full suite |
| PASS | `.venv/bin/python tools/validate_baseline.py` | DOC_STATIC_PASS,38 draft+implemented inventory operations, static documents only |
| PASS | `uv build --offline` | sdist+wheel built; verified SQL001/002/003 and connector/collection packaged |
| PASS | Fresh temporary uv venv + offline wheel install --no-deps + Database.migrate twice | M2_WHEEL_MIGRATIONS_PASS,versions[1,2,3],exit0; migration-only wheel check, not all dependency behavior |
| PASS | fixed-runtime pip-audit2.10.1 after uv export | No known vulnerabilities found,exit0; runtime lock unchanged |
| PASS | Node22 `npm --prefix frontend audit --json` |0 vulnerabilities,exit0; not image OS-layer scan |
| PASS | plain Docker backend/frontend builds | API/Worker image7731c1da9325,Frontend1b5c02aef5c0; runtime Python3.12.15,Node22 build; local Linux-arm64 |
| PASS | standalone Compose up --no-build --wait | API/Worker/Frontend all healthy; test project almrag-m2-smoke |
| PASS | API container UID/proxy/schema/default live flag | UID10001; frontend proxy health {status:ok}; schema[1,2,3]; LIVE_ENABLED False |
| PASS | `docker ... run --rm -i --network none --entrypoint python almrag-api:m2 - < tools/smoke_m2.py` | M2_OFFLINE_RUNTIME_PASS39 synthetic GET requests; temporary SQLite/assets,repeat scan,attachments,live-network deny |
| PASS | independent QA |177 full tests in13.98s before final Minor case, then new targeted1PASS in0.71s; no independent Frontend/container claim |
| PARTIAL | TDD chronology | actual correction/feature Red→Green retained; initial connection/config prototype TDD_NOT_EVIDENCED requires user review |
| NOT VERIFIED | Real ALM/TLS/renderer/deletion, real socket hard interruption, platform/process-lock matrix, shared filesystems, image OS-layer scan, remote CI | not executed or not established by these checks |

Tool execution distinctions: Docker CLI Compose plugin absent (`unknown shorthand flag`,exit125); plain docker build and installed standalone docker-compose succeeded. Colima startup first failed sandbox filesystem access, then explicitly elevated retry succeeded. UV export/wheel setup first hit cache permissions, then elevated retries succeeded. These failed attempts are not counted as product test PASS. Legacy Docker builder/deprecated package warnings were recorded without an unrelated tooling upgrade.

Source/lock files unchanged after image build except docs,CI and the standalone smoke script. Frontend final runtime image reused1b5c02aef5c0 because the new typed API client is not imported by the M1 health-only UI; native TS/client tests verify it. No M5 UI claimed. Test services were stopped and volumes retained. Colima was then stopped successfully (exit0); VM stopped, test volume retained. No database/volume deletion occurred.

No remote Push, Notion transmission, production deployment, live source call, destructive DB operation or M3 work occurred. M2_TRACEABILITY.csv maps15 Primary+6 Shared without changing assignments; GATE_MATRIX.md distinguishes later TEST-044..059 acceptance. Detailed commands are in RUNBOOK.md/TDD records and repository tools.

---

# Historical partial test evidence — 2026-10-20

Status: FAIL / BLOCKED_FOR_HUMAN_REVIEW. M2 acceptance is incomplete. All HTTP evidence below uses synthetic fixtures/MockTransport; no live ALM requests.

| Result | Command / scope | Actual observation |
|---|---|---|
| PASS | `.venv/bin/python tools/validate_baseline.py` in Main | exit0, DOC_STATIC_PASS:50 decisions/252 legacy mapping rows/59 SRS/6 subagents/36 draft operations; static documents only |
| PASS | `.venv/bin/python -m pytest -q tests/test_alm_http.py tests/test_m2_migrations.py` in Main | exit0,10 passed in0.58s; independently also run by QA |
| PASS (isolated only) | Connector specialist: `.venv/bin/python -m pytest -q` in `.worktrees/m2-connectors` | reported72 passed including34 connector tests; CONNECTOR_TDD.md preserves actual Red/Green |
| PASS (isolated only) | Collection specialist: `.venv/bin/python -m pytest -q` in `.worktrees/m2-collection` | reported58 passed including20 collection tests; COLLECTION_TDD.md preserves actual Red/Green |
| FAIL | Independent QA standalone MockTransport reproductions in QA_REPORT.md | two Major and one Minor defects reproduced; existing tests miss these cases |
| NOT VERIFIED | Main integration of connector/collection worktrees, complete M2 REST/CLI/OpenAPI/client/worker and mock E2E acceptance | not integrated/completed; no M2 acceptance claim |
| NOT VERIFIED | Live Codebeamer/Polarion compatibility, real socket timing and separate-process transport concurrency, operational rate limits, wiki POST safety | not executed |

Main connection.py and new configuration fields are untested prototypes. They were written before their intended boundary tests; they have no valid test-first completion evidence and must not be reported as completed behavior. Transport's initial module-absence Red and subsequent Green are partial evidence only; the QA counterexamples still fail the design.

No remote Push, deployment or M3 work occurred. No local container run is claimed for M2. Prior M1 evidence remains in M1/TEST_REPORT.md and does not substitute for M2 tests.

## Latest Main checkpoint after approved transport corrections

- `.venv/bin/python -m pytest -q tests/test_alm_http.py tests/test_m2_migrations.py tests/test_connectors.py tests/test_collection.py tests/test_m2_worker.py` → **92 passed in4.00s**, exit0. Includes19 transport,1 migration,41 connector,20 collection,11 worker tests. The frozen specialist files have now been copied into Main. This supersedes the earlier isolated-only state for this targeted test set, not for full milestone acceptance.
- `.venv/bin/python -m pytest -q` → **3 failed,132 passed,1 warning in8.60s**, exit1. Failures: historical M1 OpenAPI snapshot differs from in-progress M2 API;2 new API tests blocked by normalized-field/catalog mismatch OI-041. No skip/xfail or pass claim. Current M2 OpenAPI/TS generation and REST integration are incomplete.
- `.venv/bin/python tools/validate_baseline.py` →exit0 DOC_STATIC_PASS; `git diff --check` →exit0. Static spec validity does not make the failing application suite pass.
- OI-035/036/037 repair Red/Green and platform limits: TRANSPORT_TDD.md. New OI-038 two-Item independent QA/control diagnostic: ITEM_FAILURE_REPRO.md; **FAIL**, unresolved Major, implementation stopped.
- No frontend changes or new frontend test executions during this correction checkpoint. M2 packaging/container/CLI acceptance and live ALM are NOT VERIFIED.
