# Frontend M1 evidence

Main took over the specialist's configuration/tests after network/permission interruption; no unexecuted specialist result is claimed. All data and credentials in tests are synthetic.

1. Initial npm install resolved Vitest 3.2.7; audit reported 1 Moderate / 2 Critical affected packages. M1 stopped for Human Review. User then explicitly instructed “진행해” in response to the proposed Vitest 5.0.5 remediation.
2. Explicit `vitest@5.0.5` install regenerated package-lock.json. npm audit: **0 vulnerabilities**. No advisory suppression or blind force upgrade used.
3. Repeated `npm --prefix frontend test` on Vitest 5.0.5 **before App/health implementation**: exit 1, missing ./App import; 0 tests executed. This is module-absence Red evidence.
4. Implemented generated Health type + strict status decoder, safe network errors, accessible status surface. Test: **4 passed**. TypeScript/Vite build: exit 0.
5. Added typed-client tests before client implementation: exit 1, missing ./client import; existing 4 tests still passed. Implemented same-origin client, encoded identifiers, generated request/response types, bounded safe failures. Test: **6 passed**, build exit 0.
6. Clean `npm ci`: 158 packages installed, audited 159, **0 vulnerabilities**. Then 6 tests and build passed again. Separate Docker build also ran npm ci/build successfully.
7. Generated declaration: openapi-typescript 7.13.0 from docs/api/m1-openapi.json. Frontend only displays public liveness; login, source wizard and operational UI remain M5. Client wrappers cover the implemented M1 API and explicitly failing pipeline requests.

SRS linkage: SRS-027/038/040/051/052/058/059. Runtime/browser evidence is in TEST_REPORT.md. No Playwright wizard or future full UI acceptance is claimed.
