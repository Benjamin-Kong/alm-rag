# TEST-044..059 at the M2 gate

Read with the v0.2 controls in AGENTS.md, ALM_ONBOARDING.md, CHUNKING_POLICY.md, API_THROTTLING_AND_RETRY.md, FAIL_SAFE_AND_REPLAY.md and TDD_POLICY.md, plus the retained risks in docs/review/READINESS_REVIEW.md. This is a scoped gate assessment, not a claim that later-milestone acceptance tests ran.

| Test | M2 evidence / boundary | Assessment |
|---|---|---|
| TEST-044 | Source-discriminated profiles/REST/CLI negative scope tests; wizard belongs M5 | M2 foundation PASS; UI NOT VERIFIED |
| TEST-045 | Actual adapters and mock HTTP3 projects per product, original IDs, admin-only discovery | Local/mock PASS; real server NOT VERIFIED |
| TEST-046 | Tracker IDs versus Work Item Type; selected-scope revalidation | Local/mock PASS |
| TEST-047 | Field/catalog distinction, policy/scope fingerprint, stale rejection; unknown request count explicitly labeled | Local/mock PASS |
| TEST-048 | Token bound/chunk completeness | M3 NOT IMPLEMENTED/NOT VERIFIED |
| TEST-049 | Whole raw Item/side-resource payload and attachment checksums; no truncation | M2 retention PASS; chunk aspects M3 NOT VERIFIED |
| TEST-050 | Merged-table chunk atomicity | M3 NOT IMPLEMENTED/NOT VERIFIED |
| TEST-051 | Two images/three healthy services/nonroot/proxy and offline runtime | Local Linux-arm64 smoke PASS; other platforms NOT VERIFIED |
| TEST-052 | Fixed locks/native build/wheel, Python and Node audits, image builds | Local PASS; remote CI NOT VERIFIED |
| TEST-053 | Canonical server budgets, active OS slot ownership, cross-process mocks, all request classes | Local/mock PASS; real limits/distributed locks NOT VERIFIED |
| TEST-054 | Oversized429/header-first pause, Retry-After/date, auth block, timeout/circuit/deadline | Local/mock PASS; hard socket interruption NOT VERIFIED |
| TEST-055 | Two-product malformed Item sibling continuation,100/3 failures, lease/storage/auth global stop | Local/mock PASS |
| TEST-056 | Pinned refs/checkpoint/fencing foundations only; disputed public API not implemented | M4 replay/index acceptance NOT VERIFIED |
| TEST-057 | Sanitized API/CLI diagnostics, job events and heartbeat logs | M2 subset PASS; full operational views M5 NOT VERIFIED |
| TEST-058 | Actual Red/Green records; initial connection/config prototype written before tests | PARTIAL: TDD_NOT_EVIDENCED exception requires user review |
| TEST-059 | Static docs, API/client parity, ACL, rate/partial-fail/restart, local build/boot | M2 local gates PASS; full cross-milestone/remote CI NOT VERIFIED |

SRS assignments are unchanged:15 Primary and6 Shared M2 rows in M2_TRACEABILITY.csv. No missing legacy REQ clause was reconstructed. Known code findings were corrected; this table and the TDD process gap do not grant milestone approval. No M3 work started.
