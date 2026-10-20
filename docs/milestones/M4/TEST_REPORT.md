# M4 interim verification — HUMAN_REVIEW_REQUIRED

2026-10-20. Uncommitted development state, not a release candidate. Confirmed Major OI-049 prevents M4 acceptance. All evidence uses synthetic local data; no actual ALM/model, Push/Notion or production deployment.

| Result | Actual verification | Evidence / limit |
|---|---|---|
| FAIL | Independent exact original Item ID reproduction | Published opaque ID absent from title/body returns no keyword result; typed ID filter absent. OI-049 / SRS-018 |
| PASS | Independent bounded core suites |166 passed21.63s; full security/requirement acceptance not established |
| PASS | Current selection guard + indexing/retrieval/pipeline |43 passed15.34s |
| PASS | Main real synthetic local Qdrant after selection correction |4 passed1.99s; includes real process hard exit after Qdrant write/recovery, rebuild/readers/cleanup; fixture model only |
| PASS | Worker maintenance/foundation after stale regression correction |6 passed1.00s; deferred cleanup outside job heartbeat |
| FAIL (intermediate) | First integrated suite before current contract export |380 passed,2 failed,4 skipped51.84s; stale M3 schema and unsupported-SYNC assertions. Foundation assertion corrected; M4 snapshot not yet exported |
| PASS | Pipeline API/CLI/security specialist final bounded regression |26 passed5.17s in isolated tree; copied owned files to Main just before STOP. No final Main full rerun |
| PASS | Isolated frontend runtime client tests |10 passed664ms; two new missing-method Reds observed first |
| FAIL / pending integration | Isolated frontend production type build |8 new M4 schema names absent from historical M3 generated types; M4 generation not performed before STOP. Client remains isolated, not copied Main |
| PASS | Project Python baseline validator |DOC_STATIC_PASS50decisions/252legacy mappings/59SRS/6roles/42draft API; docs only, no application acceptance |
| FAIL / retained environment limit | Bare python3 tools/validate_baseline.py |System Python3.9 lacks tomllib; project Python3.12 passes |
| NOT VERIFIED | Current full API schema/client synchronization, final Main suite/QA, M4 wheel/container build/boot, complete TEST-044..059 |Interrupted by Major Human Review gate |
| NOT VERIFIED | Real models, actual ALM/TLS/rendering/deletion, remote CI/Push/Notion, other platforms and production deployment |Not executed/authorized |

Actual prior Red/Green evidence is retained in MAIN_TDD, VECTOR_TDD, LEXICAL_TDD, INDEX_TDD, PIPELINE_TDD and API_TDD. Skips, intermediate failures and isolated test counts are not promoted to Main full PASS. M3 historical reports remain historical.

Owned isolated trees .worktrees/m4-api and .worktrees/m4-client are preserved. API/CLI/security handoff reached Main immediately before STOP; frontend did not. No further source changes after OI-049 confirmation. See CORRECTION_PROPOSAL.md.

## Final corrective local evidence — 2026-10-21

Earlier interim failures remain historical evidence. OI-049 is RESOLVED within the local verified scope and M4 proceeds under the user's explicit no-further-approval M4→M6 authorization.

| Result | Actually measured final gate | Evidence |
|---|---|---|
| PASS | Main integrated Python before lastzeroChunk correction |416passed64.30s incl realQdrant; superseded by independent final below |
| PASS | Independent final Python with realQdrant |417passed64.63s exit0, noSKIP;101focused8.75s, no remaining confirmedCritical/Major |
| PASS | PublicAPI100/3partialfail/replay+correctiveedge regression |13passed10.64s |
| PASS | TS/OpenAPI/client generation, frontend test/build |10testsPASS, productiontsc/VitebuildPASS; default optionalinput semantics corrected with generatorflag; noM5UI |
| PASS | Baseline validator + diffcheck |DOC_STATIC_PASS44draftAPI operations, docs-only; 6Primary+9Shared M4trace rows |
| PASS | sdist/wheel + fresh isolated no-deps offline install |requiredM4modules/005/006 present; migrate twice1..6,M4_WHEEL_MIGRATIONS_PASS |
| PASS | Corrected runtime dependencies |certifi2026.10.19 installed;69HTTP/security/vector/modelruntime testsPASS2.11s |
| FAIL then PASS | Runtime pip-audit |First1known certifi vulnerability GHSA-6q48-6c7w-9gw2; singlepackage lockfix→No known vulnerabilities found(exit0) |
| PASS | Node22 npm audit |0vulnerabilities exit0 after sandboxDNSretry |
| PASS | Final local images |Backend cd02797a39db includescertifi2026.10.19; frontend1b5c02aef5c0; localLinux-arm64 |
| PASS | Final local Compose boot |3healthyservices, backendUID10001/schema1..6/liveALM+model+vector allfalse |
| PASS | Final backend --network none tools/smoke_m4.py |55chunks13contentembeddingrequests/repeat0/FIXTURE_ONLY; actualSQLiteFTS+indexpublication+exactID/filter/hybrid/detail with syntheticinmemoryvector |
| NOT VERIFIED | ActualALM/model/artifacts/calibration/retrievalquality, nativeWindows/Linux-amd64, OSimageaudit, remoteCI/Push/Notion/productiondeployment |Not executed or not authorized; model fixture !=realmodelPASS |

Advisory source: https://github.com/advisories/GHSA-6q48-6c7w-9gw2 . Firstauditfoundissue was not treatedasPASS. uv cache/registry/sandboxtransport failures were retried with authorizedpermissions. A mistyped test_transport.py command ran0tests; corrected test_alm_http.py produced the69PASS above. ExistingDockerlegacybuilder andwhatwg-encoding deprecationwarnings retained as toolinglimits.
