# TEST-044..059 at the M3 gate

Scope: current local unit/integration/mock acceptance and explicitly measured runtime. Follow v0.2 controls, TDD_POLICY and the v0.2 READINESS_REVIEW. Q01~Q50 and Primary/Shared assignments are unchanged. Never substitute this table for full cross-milestone acceptance.

| Test | Actual M3 evidence / boundary | Assessment |
|---|---|---|
| TEST-044 | Existing source-discriminated API/CLI schemas and ACL regressions retained | Backend PASS; M5 React wizard NOT VERIFIED |
| TEST-045 | Existing M2 actual adapter/mock discovery/secret/error regressions retained | Local/mock PASS; actual ALM/version NOT VERIFIED |
| TEST-046 | Tracker versus Work Item Type remains distinct | Backend PASS; selection UI M5 |
| TEST-047 | M2 source preflight retained; M3 processing-preflight reads stored inputs/pins runtime+policy without ALM calls | Local/mock PASS; actual source estimate NOT VERIFIED |
| TEST-048 | Exact full-input bounds, source15k local WordLevel+BOS, synthetic context clamp, model count mismatch; OI-047 resolved | Local PASS; deployed model/tokenizer/context NOT VERIFIED |
| TEST-049 | Full original fields/HTML immutable;15k paragraph+100data-row merged table and all char/UTF8/cell spans; raw DB recovery verified | M3 local retention PASS; active detail API restoration M4 NOT VERIFIED |
| TEST-050 | Header hierarchy/merged grid/row and cell association, oversized cell spans; ambiguity explicitly fails locally | Local PASS; unsupported general nested/group fallback not implemented |
| TEST-051 | M3 images built,3healthy/nonroot services,proxy/schema1..4, network-none runtime | Local Linux-arm64 PASS; other platforms NOT VERIFIED |
| TEST-052 | Frozen install/locks, sdist/wheel and fresh offline migration install, Python/Node audit0 | Local PASS; image OS-layer scan/remote CI NOT VERIFIED |
| TEST-053 | Existing shared ALM transport/budget/OS-held slot/429 regressions retained; M3 processing makes no source calls | Local/mock PASS; actual shared/distributed limits NOT VERIFIED |
| TEST-054 | Existing Retry-After/auth/deadline regressions; model auth/429/schema/count failures tested separately | Local/mock PASS; hard synchronous socket interruption NOT VERIFIED |
| TEST-055 |100Items/3parser failures→97ready, all100raw+3stage/revision failures; separate embed-local error, storage/integrity/lease global stop | M3 local PASS; full SYNC/replay/active search acceptance M4 |
| TEST-056 | Fenced job reclaim, partial vector cache resume, no false EMBED_READY | M3 foundation PASS; public replay/atomic index publication M4 NOT VERIFIED |
| TEST-057 | Sanitized API/CLI/model codes, job state/events, worker heartbeat retained | Local subset PASS; real process hard-kill M3/model request not run, operational UI/public failed-item routes later |
| TEST-058 | Actual specialist/Main Red→Green, including OI-0473FAIL→Green, honest E2E-regression chronology | M3 scoped PASS; M2 initial prototype TDD_NOT_EVIDENCED retained/accepted exception |
| TEST-059 |271Python+8Frontend tests, current M3 OpenAPI/type-client parity, negative ACL, local Docker/lock/audits/offline smoke; CI definition updated | Local PASS; remote CI NOT VERIFIED |

AC-02's Qdrant payload update, AC-03's distinct search Item, AC-05's active-generation search safety, AC-10's active Item API restoration and AC-12's full SYNC/public per-Item replay are not claimed as M3-complete. M3's stored-source/chunk/cache subsets are tested; M4 owns index/search/publication/replay. Primary10+Shared7 rows are in M3_TRACEABILITY.csv. Legacy original REQ clauses remain NOT VERIFIED.
