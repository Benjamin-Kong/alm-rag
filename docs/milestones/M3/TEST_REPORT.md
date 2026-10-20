# M3 final local test report — 2026-10-20

All current executable checks below passed within their stated scopes; approval is pending. Earlier FAIL evidence is retained in QA_REPORT/MAIN_TDD/TOKENIZER_REVALIDATION/MOCK_E2E_TDD. Synthetic data only, no live ALM/model traffic or weights.

| Result | Actual command / scope | Observed evidence |
|---|---|---|
| PASS | `.venv/bin/pytest -q` |271passed33.68s,exit0, no skipped/xfail |
| PASS | Independent QA full suite |271passed33.18s; no confirmed remaining Critical/Major in bounded review |
| PASS | `tests/test_m3_mock_e2e.py` |4passed9.68s; real API/queue/worker/adapters/SQLite with mock HTTP,15k+100row/oversized cell, zero-repeat-embedding,100/3parser isolation, real local tokenizer artifact regression |
| PASS | Node22 `npm ci`, generation, test/build |8tests, TypeScript/Vite production build; current M3 OpenAPI regenerated client |
| PASS | `uv sync --frozen` |44packages audited15ms; no dependency changes |
| PASS | `.venv/bin/python tools/validate_baseline.py` |DOC_STATIC_PASS50decisions/59SRS/6roles/42API inventory, docs only |
| PASS | Exported actual API snapshot + typed client/negative ACL tests |m3-openapi.json executed schema26operations; historical m1/m2 snapshots preserved |
| PASS | `uv build` + fresh uv venv/offline wheel install --no-deps, migrate twice |sdist/wheel built; required M3 modules+004SQL present; M3_WHEEL_MIGRATIONS_PASS versions1..4. Migration-only isolated wheel check, not isolated full-dependency behavior |
| PASS | Runtime export + pip-audit2.10.1 |No known vulnerabilities found,exit0 |
| PASS | Node22 npm audit |0vulnerabilities,exit0 after network-enabled retry; language package audit only |
| PASS | Docker backend/frontend builds |API/Worker bf5b8fb5796d; Frontend1b5c02aef5c0; Linux-arm64 Python3.12.15/Node22 build |
| PASS | Compose almrag-m3-smoke up --no-build --wait |API/Worker/Frontend3healthy; UID10001/10001/101; schemas[1,2,3,4]; proxyhealth; default live ALM/model bothfalse |
| PASS | M3 backend `--network none` stdin tools/smoke_m3.py |M3_OFFLINE_RUNTIME_PASS55chunks/13content embedding requests/repeat0/FIXTURE_ONLY; actual pinned local WordLevel15k+BOS/100row fixture/mocks/temporary SQLite |
| PASS | Same image M2 runtime regression |M2_OFFLINE_RUNTIME_PASS39syntheticGET; original raw/attachments/repeat observations/shared transport still work with migration004 |
| PASS | Diff whitespace + source trace review |git diff --check; exact10Primary+7Shared M3 rows, no assignment/legacy-clause invention |
| FAIL / retained environment limitation | Bare system Python3.9.6 baseline command |tomllib absent; project Python3.12 command passes. Use project runtime, not a fake application PASS |
| NOT VERIFIED | Real model/tokenizer calibration/context/vector quality; actual ALM/TLS/wiki rendering/confirmed deletion; Qdrant/index/search/M4; native Windows/Linux-amd64; OS image scan/shared-filesystem locks; remote CI/Notion/Push |Not executed or not established by these checks |

Sandbox retry evidence: uv cache initially denied during wheel/frozen sync, Docker socket denied for Compose/stdin smoke, npm audit registry DNS failed. Authorized elevated retries succeeded. These failed attempts are environment observations, not application success. Docker legacy-builder and npm whatwg-encoding deprecation warnings remain tooling backlog; no unrelated tool upgrade was performed.

Frontend final runtime image reused prior digest because the typed client is not consumed by the health-only UI and no M5 UI is implemented. The Docker build compiled current generated types and current native client tests passed; neither means a processing wizard exists. Compose smoke was stopped after verification while retaining its named volume; no DB/volume deletion. Colima was already running when this turn started it, so the shared dedicated VM was left running.

Independent QA ran the Python/static/diff and bounded code review; the container/wheel executions above are Main's measurements, not independently rerun QA claims. TDD records distinguish genuine feature/correction Reds from regression tests that passed on their first run. No active revision or index generation was published. No production deployment or external source connection occurred.
