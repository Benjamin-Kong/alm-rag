# M2 Main evidence — 2026-10-20

## Initial transport and ordered migrations

Initial transport test collection failed because almrag.alm_http did not exist (module-absence Red). Subsequent tests reached Green; an initial nonretryable-auth test incorrectly reused a globally blocked credential and was corrected to use separate identities. Explicit persistent401 regression was added. Main's transport+migration tests10 PASS before remediation do not cover the QA failures; see TRANSPORT_TDD.md for authorized corrective Red/Green evidence when available.

## REST integration in progress

SRS-001/003/045/046/047/053/055. New tests/test_m2_api.py uses actual SQLite, actual adapters and ALMHttpClient with synthetic HTTP MockTransport, no live sockets.

- Actual Red: `.venv/bin/python -m pytest -q tests/test_m2_api.py` →5 setup errors in0.35s, create_app lacked connections/collection injection. API routes did not exist.
- Minimal routes/models/administration/service injection added. Actual next run →2 failed,3 passed in1.58s. Failures expose the numeric Codebeamer source-field ID versus normalized title/description namespace mismatch; NOT GREEN, not completed API acceptance. No results fabricated or marked passed.
- Existing connection.py and config prototype predated these tests; test-first evidence is absent for their original creation. Tests now exercise the boundary but cannot retroactively prove Red for prototype internals.
- Integration implementation paused for review of newly reported Item-local/global error-boundary defect. OpenAPI/client have not yet been refreshed; new routes must not be treated as finalized contracts.

## Integrated module checkpoint

Actual Main command `.venv/bin/python -m pytest -q tests/test_connectors.py tests/test_collection.py tests/test_m2_migrations.py` →55 passed in1.86s before subsequent connector error-bridge tests were copied. This is partial integration evidence, not whole M2 acceptance. Frozen specialist Red/Green records reside in CONNECTOR_TDD.md and COLLECTION_TDD.md.

## Approved integration correction and actual new executions

User “보완하고 계속 진행해”, then “계속 진행해”, authorized the OI-038/039/040/041 corrections. Two original specialists hit account usage limits before returning final evidence. Main preserved their artifacts, copied their new tests first into Main while old implementation remained, and ran actual Red rather than inventing the missing specialist results.

- `.venv/bin/python -m pytest -q tests/test_collection.py tests/test_item_failure_integration.py` →**12 failed,32 passed in2.72s** before copying corrected source. Six collection failures cover separate normalized/source IDs, unknown request estimate/lower bound, policy fingerprint and scoped field identities/legacy preservation. Six Item conversion failures cover both products' fields/descriptions/relations; global-control cases already passed.
- Copied the isolated corrected collection.py and connectors module. Next combined run reached1FAIL/89PASS: integrated transport invoked lease guard while holding its write transaction. Added a focused nonblocking SQLite callback test before fixing: **1 failed,19 deselected in0.22s**, database is locked. Avoid calling abort callback under the transport write lock; check elapsed deadline there and check abort before/after transaction.
- After that fix: `.venv/bin/python -m pytest -q tests/test_alm_http.py tests/test_m2_api.py tests/test_collection.py tests/test_item_failure_integration.py tests/test_connectors.py tests/test_m2_cli.py` →**115 passed in5.27s**. Existing M1 contract parity was then refreshed for the current M2 snapshot while preserving the historical M1 file; full Python suite **165 passed in9.86s**.

## CLI and generated client

- tests/test_m2_cli.py actual Red:4FAIL in0.34s; with login/session binding case added before implementation5FAIL in0.28s. Added source/project registration, discovery, source-specific scope config, preflight and COLLECT, HTTPS admin login and0600 API-bound session file; no browser dependency. Actual Green:5PASS in0.18s.
- Frontend new typed-client contract test: **1 failed,6 passed**, discoverProjects missing. Generate from m2-openapi.json, extend client methods and typed COLLECT Job response:7PASS. Build first failed because generated Stage requires force; test input corrected to explicit force:false. TypeScript/Vite build then PASS. No M5 wizard implemented.
- tests/test_m2_mock_e2e.py adds coverage for existing behavior, not a new behavioral change: **6PASS in4.38s**. Actual API/admin/SQLite/shared HTTP MockTransport/product adapters/Worker and attachment persistence across two scans for3 projects per product; complete pagination and raw payload retained. No sockets.

## Third QA corrective checkpoint: equivalent origins and attachment path

Independent QA reproduced Major OI-042(default443 profiles bypass same-server pause) and Minor OI-043(worker ignores configured asset path). User subsequently instructed “진행중인가? 계속 구현해”; Main announced the concrete fixes and resumed within M2.

- New alias/default80+443/profileidentity/legacy-pause tests: **4FAIL,25 deselected in0.67s**. New Worker/root-default tests: **2FAIL,13 deselected in0.28s**.
- Canonical URL/origin shared by profiles, rate policy, allowlist, budget and OS locks; profile registration updates instance/profile atomically. Existing prototype noncanonical budget state fails closed with SERVER_ORIGIN_MIGRATION_REQUIRED; no automatic DB merge or lock migration. Worker and API share Settings.attachment_directory; default follows database-parent/attachments, explicit path preserved.
- `.venv/bin/python -m pytest -q tests/test_alm_http.py tests/test_m2_api.py tests/test_m2_worker.py tests/test_config.py` →**44 passed in3.93s**. Independent verification requested; do not treat Main result as independent QA.

Independent QA then confirmed177 full tests PASS in13.98s and the original equivalent-origin/asset-root reproductions corrected. Same round found one Minor invalid-port500. New tests/test_m2_api.py::test_invalid_url_port_is_validation_error_without_registration actually failed1/6deselected in0.51s (500). canonical_endpoint now translates httpx.InvalidURL into a sanitized Pydantic ValueError; Green1PASS in0.56s, independent Green1PASS in0.71s. Final Main fullsuite178PASS in14.50s. No known code finding remains unresolved within tested scope; initial-prototype chronology exception remains explicit.
