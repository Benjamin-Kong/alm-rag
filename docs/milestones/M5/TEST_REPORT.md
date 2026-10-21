# M5 test report — 2026-10-21

Status: LOCAL_PASS_WITH_DOCUMENTED_LIMITATIONS. Synthetic fixtures only. This is application evidence, separate from the static baseline validator.

| Check actually executed | Result |
|---|---|
| Root full Python, dedicated local Qdrant enabled | 466 PASS / 70.43s, no SKIP; final additional roundtrip included |
| Additional API→worker→ZIP download/upload/import→admin nonce recovery roundtrip | 1 PASS / 1.36s |
| Independent Python final | See QA_REPORT.md |
| Frontend Node22 unit / TypeScript / production build | 24 PASS, 7 files; build PASS |
| Actual local Chromium, mocked API | 7 PASS / 5.4s; wizard both products, project permissions, search XSS, replay, nonce recovery |
| Operations corrective tests | 31 PASS / 2.87s; independent adversarial rechecks PASS |
| Worker/corrective terminal-owner regressions | 31 PASS / 3.99s |
| uv build / isolated offline wheel | sdist+wheel PASS; fresh temporary venv, no-index/no-deps installation, migrations1..8 twice PASS |
| Final Docker build / Compose boot | backend dbde1a9a030b; frontend ae386654cc79; three services healthy; API uid10001 |
| Final image network-none smoke_m5 | PASS, 39 synthetic GET requests; actual collector/ZIP/recovery path |
| Container security/runtime observations | certifi2026.10.19; live ALM/model/vector/Notion flags all false; schema1..8 |
| Node audit | 0 vulnerabilities |
| Static baseline | PASS, 53 draft/API operations, YAML/TOML; documentation evidence only |

Commands: `env ALMRAG_TEST_QDRANT_URL=http://127.0.0.1:16333 .venv/bin/pytest -q`; Node22 `npm --prefix frontend test`, `npm --prefix frontend run build`, `npm --prefix frontend run test:e2e -- --timeout=10000`; `uv build`; `.venv/bin/python /private/tmp/almrag-m5-wheel-check.py`; Docker context colima-alm-rag, image almrag-api:m5 network none with tools/smoke_m5.py; compose project almrag-m5-smoke up --no-build --wait. No production deployment.

Historical FAILs remain in MAIN_TDD/OPERATIONS_TDD/FRONTEND_TDD. Initial browser native fetch binding and control labels failed, then were corrected before the final 7 PASS. One new roundtrip test incorrectly expected empty recovered auth tables; fresh recovery intentionally has no auth tables. Corrected the assertion, not production behavior. Two container inspect commands used an incorrect Settings property / closed context; corrected SQL inspection confirmed schema1..8. The first sandbox wheel command hit uv macOS system-configuration panic; elevated offline rerun passed. These are not application PASS claims for the failed commands.

NOT VERIFIED: actual customer ALM/wiki renderer, actual embedding model/tokenizer/quality, remote Notion delivery/permissions/exactly-once under eventual consistency, production HTTPS deployment, other host OS/native architectures, remote CI and OS-image advisory scan. Recovery is RAW_ONLY_REBUILD_REQUIRED in a new directory with auth REREGISTRATION_REQUIRED; vectors are regenerated and live database is never replaced. UI HTML bound is 1,048,576 UTF-16 code units, 10,000 nodes/depth100; rejected preview does not truncate retained original. M2 historical TDD_NOT_EVIDENCED remains.
