# M1 test report — pending Human Approval

Date: 2026-10-20 (Asia/Seoul). Applicable M1 foundation checks passed. Product-wide SRS tests and unexecuted environments remain separate.

| Status | Check | Actual evidence |
|---|---|---|
| PASS | Python unit/integration/mock foundation | Main and independent QA: `.venv/bin/python -m pytest -q` → **38 passed**, one Starlette/httpx deprecation warning. No skips/xfails. |
| PASS | Actual database/process recovery | Migrations, WAL/FK, source identity, immutable revisions, same-project generation ownership, global FIFO, 3-process claim exclusion, actual child termination after checkpoint, replacement lease/fencing. Tests use temporary SQLite only. |
| PASS | Auth/secrets/audit | Secure sessions/expiry/CSRF, scoped hashed keys, revoke/anti-escalation, input/error secrecy, encrypted secret references, safe diagnostics, real caller/target/trace and mutation rollback on audit failure. |
| PASS | API/worker mock acceptance | Actual migrated DB + API + worker reason/events + scoped negative reads. Independent CLI and worker process executed. Missing real stage handlers block instead of falsely succeeding. |
| PASS | Frontend unit/typed client | Main and QA: **6 passed** across 2 files, strict health response decoding, safe failures, same-origin encoded requests. |
| PASS | Frontend reproducible install/build | Clean `npm ci`: installed 158/audited159 packages, 0 vulnerabilities; TypeScript check and Vite production build exit0. Docker repeated npm ci/build. |
| PASS | Native wheel contents/install | `uv build --wheel` exit0, SQL migration present in wheel. Installed that local wheel with no dependencies/network into a clean uv-created temporary environment; actual migrate twice returned WHEEL_MIGRATION_PASS. |
| PASS | Baseline static + scope regression | DOC_STATIC_PASS: 50 decisions, 252 legacy rows, 59 SRS, 6 roles, 36 draft API operations. Dependency negative-YAML fixture exclusion and authored-invalid-YAML rejection tested. Static PASS is not application proof. |
| PASS | API artifact parity | Executable API JSON and main OpenAPI implemented subset match the executed app; generated TS declaration compiled. Generation is reproducible; future routes remain marked draft. |
| PASS | API/Worker image | Final Docker build exit0: **a4968323087a**, frozen uv.lock runtime install, Python3.12.15, UID10001. One image is shared by API and worker. |
| PASS | Frontend image | Final Docker build exit0: **1b5c02aef5c0**, digest-pinned Node/Nginx, non-root UID101. |
| PASS | Compose build/boot/health | Project almrag-m1-smoke: API, worker and frontend all Healthy after final images. Actual Frontend→Nginx→API health returned {status:ok}; static HTML served. |
| PASS | Persistence | Synthetic project inserted into dedicated test volume; API/worker restart retained source_project_id fixture-42 count1. No production state used. |
| PASS | Real browser smoke | Codex in-app browser opened localhost:8080; actual AX tree showed ALM RAG, 서비스 연결 and **Available**. No credentials entered. This is manual smoke, not the M5 Playwright wizard suite. |
| PASS | Python runtime audit | Initial cryptography46.0.7 reported7 advisory entries. Updated lock to50.0.2; pip-audit2.10.1 on exported frozen runtime dependencies: exit0, No known vulnerabilities found. |
| PASS | Frontend security remediation | Initial audit3 affected packages (1Moderate/2Critical) triggered Human Review. User approved Vitest5.0.5 remediation; updated lock audit0, no suppression/force fix. |
| PASS | Independent final QA | QA independently repeated38 Python+6 Frontend tests and static gate. Audit Medium fixed. No unresolved concrete Critical/Major/Medium found in bounded M1 foundation review. |
| NOT VERIFIED | Remote CI | Workflow defines tests, audits, schema drift and container boot. It was not pushed or executed on GitHub. Local equivalents above are separate evidence. |
| NOT VERIFIED | Environment/security matrix | Windows/native Linux, AMD64 containers, image OS-layer vulnerability scan and external service/TLS environments not exercised. macOS Python3.12.12 and Linux-arm64 containers were exercised. |
| NOT VERIFIED | Future product behavior | Real ALM, full EmbeddingGemma compatibility, hybrid retrieval, actual publication, complete Item replay, wizard, backup/import and performance remain assigned later milestones. |

Code/test/SRS mapping: M1_TRACEABILITY.csv and added M1 columns in docs/requirements/TRACEABILITY.csv. Full product tests TEST-017/023/025/044/056/057/059 are not promoted to blanket PASS by foundation subtests. TDD details and observed failures are in MAIN_TDD.md, STORAGE_TDD.md and FRONTEND_TDD.md.

Warnings: Starlette/httpx test adapter deprecation; whatwg-encoding dev dependency deprecation; Docker legacy builder deprecation and fixed UID useradd range warning. None prevented observed commands. No deprecated Codex config key was changed. Image OS/package scan coverage is explicitly limited above.

Additional environment observation: a stdlib `venv(with_pip=True)` smoke attempt aborted in ensurepip both sandboxed and elevated. The documented project-standard `uv venv` + offline local-wheel install succeeded; the failed ensurepip attempts are not counted as PASS. A basic local private-key/GitHub/OpenAI token pattern scan found no matches; it is not a complete DLP guarantee.
