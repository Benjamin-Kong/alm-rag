# M6 final test report — 2026-10-21

LOCAL_QUALITY_VERIFIED_WITH_DOCUMENTED_LIMITATIONS. Results distinguish actual application tests, synthetic workload measurements and unavailable external integration. No remote Push/Notion, actual customer ALM/model or production deployment performed.

| Actual check | Attribution | Result |
|---|---|---|
| Full Python regression, dedicated real local synthetic Qdrant | Independent read-only QA | **506 PASS /77.45s**, exit0, no SKIP |
| Integrity/Chunk/API/worker/mock E2E correction review | Independent QA |61 PASS /3.61s|
| Exact-ID bounded SQL-work/retrieval/filter/quality regression | Independent QA |46 PASS /5.76s; root46 PASS /5.80s|
| Actual Qdrant golden evaluation and remote vector corruption detection | Independent QA |1 PASS /0.80s; root1 PASS /0.74s|
| Frontend Node22 unit | Independent QA |28 PASS /9files /1.35s; root28 PASS /1.30s|
| TypeScript and Vite production build | Independent QA |PASS715ms; root PASS690ms|
| Actual Chromium | Root |**10 PASS /8.2s**:9mockAPI flows +1actual native HTTPS API/session/CSRF/FIFOworker/report/logout|
| Synthetic100kItem capacity and actual SearchService/SQLite/Qdrant workload | Root; raw result audited by QA |100000Items/199999Chunks/199999points; all100queries top10, exact ID first100/100; PRAGMA integrity ok/foreignkeys0|
| Synthetic latency initial→corrected | Root |P95 **4.301129s FAIL→1.374950s PASS**, identical100exactIDsamples5warmups; initial output retained|
| uv build / offline fresh wheel | Root |sdist+wheel PASS; no-index/no-deps isolated install, schema1..9 migrate twice PASS|
| Final Docker images | Root |backend5ef1d80a93a9 / frontendcf454e02335a; Linuxarm64 builds PASS|
| Compose API/worker/frontend | Root |3healthy, API UID10001/frontendUID101; schema1..9, certifi2026.10.19; all liveALM/model/vector/Notion flags false; frontend API proxy status:ok|
| Final image network-none M6 smoke | Root |PASS39syntheticGET; ZIP Export/Import/raw recovery/nonce/integrity runtime|
| Final image M2/M3/M4 regression smokes | Root |M2 PASS39syntheticGET; M3/M4 eachPASS55Chunks/13contentembeddings/repeat0/FIXTURE_ONLY|
| Python/Node package audits | Root |No known vulnerabilities / Node0; unchanged frozen locks|
| Static baseline/release evidence/diff | QA +Root |PASS55executableAPI operations; TDD document/CI presence WITH historical M2exception; not application test evidence|

Executed commands: `env ALMRAG_TEST_QDRANT_URL=http://127.0.0.1:16333 .venv/bin/pytest -q`; Node22 `npm --prefix frontend test`, `npm --prefix frontend run build`, `npm --prefix frontend run test:e2e -- --timeout=10000`; `uv build`; `.venv/bin/python /private/tmp/almrag-m6-wheel-check.py`; Docker context colima-alm-rag builds/compose project almrag-m6-smoke up --no-build --wait; final image `--network none` with tools/smoke_m2.py..smoke_m6.py; static tools/validate_baseline.py and tools/validate_release.py. Current executable contract docs/api/m6-openapi.json, historical m1..m5 preserved; type client synchronized.

FAIL history retained, then corrected: strict JSON bool/int equality; normalized text/table mutation and dropped source spans; mutable quality request; omitted stage names; native fetch/form Unicode-v pattern; stale async evaluation response; top_k boolean coercion; exact-ID generation-wide point scan. See MAIN_TDD/ENGINE_TDD/BENCHMARK_TDD and QA_REPORT. No unrun Red/Green or independent packaging/browser execution claimed. The first native HTTPS failure was testfixture static dispatch behind API auth; product auth/ACL was not relaxed. Sandbox port/uv/system-info restrictions were resolved with approved local reruns; a subagent approval wait did not count as a benchmark execution.

NOT VERIFIED: actual ALM/version/wiki renderer behavior, actual calibrated Ollama/tokenizer/model quality/context/token recount, human-judged20–50query golden quality, production100k collection/normalization/embedding/integrity pipeline, actual CPU/GPU/remote embedding, actual warm-Ollama P95, Windows/nativeLinux/amd64/remote Qdrant deployment, productionTLS/rollout, actual Notion delivery/permissions, remote CI and OS image vulnerability scan. The100kfixture is direct retrieval-shape data with generated1/2/3Chunks and constant2D vectors, not production-valid processing artifacts; latency is exact-ID workload only. M2 OI045 TDD_NOT_EVIDENCED and original legacy REQ clause limitations remain. Backup restore remains isolated raw-only with auth re-registration and index rebuild; never replaces the live DB.

Final runtime regressions: M2imagePASS39syntheticGET; M3/M4images eachPASS55Chunks/13contentembeddings/repeat0/FIXTURE_ONLY. Latest APIUID10001/frontendUID101/schema1..9/certifi2026.10.19/flagsallfalse rechecked after imageupdate. All testCompose services and dedicatedsyntheticQdrant stopped; volumes retained, Colima VM untouched.

## Later remote Linux CI evidence — 2026-10-21

Commit531ff5d passed GitHub-hosted Ubuntu24.04 amd64 run39547347678:506Python/28frontend/10Chromium, audits0, contract diff,3healthyservices andM2..M6network-none smokes. This supersedes earlier remoteCI/amd64 NOT VERIFIED statements only for that tested scope; user Linux host/actualALM/model/OSimage scan remain NOT VERIFIED. See [REMOTE_CI_REPORT.md](REMOTE_CI_REPORT.md) for actual Red/Green and limits.
