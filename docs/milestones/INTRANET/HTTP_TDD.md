# Explicit intranet HTTP — actual TDD evidence

SRS019/027/038/051/059. User approved HTTP intranet deployment and authentication configuration change in current request.

Red: `.venv/bin/pytest -q tests/test_intranet_http.py` actually4FAIL/1PASS0.88s before implementation: no opt-in enforcement/config flag, no intranet session support. Existing defaultHTTPS case passed and retained. New cases verify HTTP same-origin login/cookie roundtrip, missingCSRF/wrongOrigin403, logoutcookie removal and revoked session401; opt-in HTTPS retainsSecure. Green results appended after execution.

- Initial HTTP implementation: newHTTPtests5PASS; combined17PASS/1FAIL2.80s was expected stale generated auth description, then OpenAPI exported. Persistentservertests first2FAIL0.28s missingmodule; implementation19PASS/1FAIL3.18s because StaticFiles404 exception lacked handler outsideFastAPI. Added boundedstaticerrorresponse, traversal tests retained.

- Persistentserver+HTTP/config/API combined20PASS3.31s. CLIHTTP test actual1FAIL/5PASS1.01s: CLI unconditionally requiredHTTPS. Added explicit flag+matchingOrigin transport check for login and persisted session requests, sameAPIURL file binding retained; defaultplainHTTP rejection preserved.

- Final targeted HTTP/server/API/config/CLI26PASS3.39s; integrated target71PASS3.40s; full558PythonPASS77.69s/noSKIP with dedicatedsyntheticQdrant. Frontend28PASS/build712ms. Actual11ChromiumPASS9.6s:9mockAPI +1nativeHTTPS +1explicitHTTP, both session/CSRF/worker/report/logout. No realALM/model access.
