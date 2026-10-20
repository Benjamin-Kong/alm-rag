# M1 independent QA report

Status: **TECHNICAL FOUNDATION PASS — PENDING HUMAN APPROVAL**. Date: 2026-10-20. QA does not approve the milestone on the user's behalf.

## Independent checks

- Final read-only QA ran **38 Python tests PASS**, one Starlette/httpx deprecation warning; **6 Frontend tests PASS**; DOC_STATIC_PASS, exit0.
- Confirmed actor attribution uses the actual admin/session or scoped API principal, hashed actor_ref, target key UUID and request trace. Key mutation and audit share one transaction; failure rollback test passes.
- Frontend health accepts only the expected response and does not render server error bodies. Generated API snapshot parity is tested; same-origin client request types compile.
- No unresolved concrete Critical/Major/Medium defect found in the bounded M1 foundation review. Future product behavior remains unverified rather than silently accepted.

## Findings and disposition

| Finding | Severity | Disposition |
|---|---|---|
| Auth lookup/audit SQLite failures escaped sanitized boundary | Medium | Cycle1: actual fault-injection Red2 failures, boundary expanded, regression PASS |
| Audit actor/target omitted; API used literal admin | Medium | Cycle2: Red2 failures, actual opaque caller/target/trace + atomic event persistence, regression PASS and independently verified |
| Initial Frontend Vitest/Tinypool development tool chain | Critical | Immediate Human Review stop. User explicitly approved proposed remediation. Vitest5.0.5 lock + npm audit0 + clean install/test/build PASS. No risk acceptance or suppression. |
| Baseline validator parsed vendor malformed YAML fixtures | Medium tooling | Red2 failures/1pass, authored-file-only traversal and .yml support, 3pass + static PASS |

Initial critical package details: @vitest/mocker GHSA-82fw-gwwq-j7x9; tinypool GHSA-5gmw-xhrv-c9v3 and GHSA-85c8-ppgw-ccpr; vitest package severity aggregate. Audit3 affected packages meant1Moderate/2Critical package findings, distinct from advisory count. No exploitation/data exposure observed.

## Evidence boundaries

Container build/boot, browser smoke, volume persistence and vulnerability scans were performed by Main and are documented in TEST_REPORT.md. QA did not independently repeat those environment actions. GitHub-hosted CI, image OS-layer scan, real ALM/model/index and future milestone scenarios are NOT VERIFIED.

QA considered M1's existing foundation boundaries: real handlers stay unavailable; M2 source discovery, M3 processing/model, M4 publication/search/replay and M5 operational UI are not claimed implemented. TEST-044..059 full scenarios retain their assigned later gates; M1 schema/container/TDD portions are traced separately.

Requirements/architecture specialist read-only scope review preceded implementation. Storage/frontend used isolated worktrees and explicit Main handoff. No production code was modified by QA. The user must approve M1 before M2.
