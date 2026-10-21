# Remote Linux CI revalidation — 2026-10-21

Tested commit: `531ff5de28c0a9de6df0e871004953d1168ec869` on `codex/m6-quality`.

[Successful run 39547347678](https://github.com/Benjamin-Kong/alm-rag/actions/runs/39547347678), job foundation119048408865, UTC05:02:49–05:06:54, conclusion SUCCESS. GitHub-hosted Ubuntu24.04 amd64, Python3.12, Node22; source checkout and frozen dependency install were executed on the runner. This is actual Linux runner execution, separate from the user's future Linux host.

## Actual results

| Gate | Status | Evidence |
|---|---|---|
| Baseline / release evidence | PASS with documented exception | static presence only; M2 OI-045 TDD_NOT_EVIDENCED retained |
| Python + dedicated Qdrant | PASS | 506 passed, 3 warnings, 106.99s; no skipped tests |
| Python runtime dependency audit | PASS | No known vulnerabilities found |
| OpenAPI export + generated contract diff | PASS | generated files match committed contracts |
| Frontend unit + production build | PASS | 28 tests /9files, TypeScript and Vite succeeded |
| Chromium browser | PASS | 10 passed 11.5s;9mockAPI +1actual nativeHTTPS/API/session/CSRF/worker |
| Browser evidence upload | PASS | synthetic-browser-evidence, seven-day retention |
| Node dependency audit | PASS | 0 vulnerabilities |
| Linux amd64 image build/boot | PASS | API, worker and frontend all Healthy; frontend-proxied health request succeeded |
| Network-none M2 image smoke | PASS | 39 synthetic GET requests |
| Network-none M3/M4 image smokes | PASS | each55chunks/13fixture embedding requests/repeat0 |
| Network-none M5/M6 image smokes | PASS | each39syntheticGETrequests |
| CI-owned test cleanup | PASS | dedicated CI Compose stack/volumes removed |

[Uploaded synthetic browser artifact](https://github.com/Benjamin-Kong/alm-rag/actions/runs/39547347678/artifacts/12322675835) ZIP SHA256: `7712790c12371823c4a39fe04a2ca08e1e6b2bb11807ba5a742cf1bef20f7e30`. Retention is bounded; long-term evidence is this result summary and run reference. No customer data or real credentials were used.

## Retained Red and review

[Initial run39545808983](https://github.com/Benjamin-Kong/alm-rag/actions/runs/39545808983) FAILED:9browserPASS/1FAIL because screenshot used macOS-only /private/tmp. Downstream gates were skipped. OI-063 correction uses Playwright testInfo.outputPath, no assertions removed or skipped. Local10PASS8.2s; independent read-only QA approved bounded diff and2release testsPASS. Remote Green above closes OI-063 within this scope.

## Limits and follow-up

- Actual customer Linux server download/manual UI/installation: NOT VERIFIED; use [Linux procedure](../../LINUX_VALIDATION.ko.md). User selected this as priority2 before actual ALM/model testing.
- Actual ALM, calibrated Ollama/tokenizer/semantic quality, production100k processing, customer TLS/recovery, image OS vulnerability scan, Windows and actual Notion delivery: NOT VERIFIED. Runtime package audits do not cover image OS packages.
- Runner reported action Node20 runtime deprecation (forcedNode24) and upcoming ubuntu-latest migration. This successful run used Ubuntu24.04; future runner environments are not covered. Track action-runtime/runner maintenance separately, without treating these warnings as test failures.
- Prior reports describing remote CI as NOT VERIFIED are historical local-completion snapshots; this report is the later evidence for the tested SHA only. Default main was not merged and no production deployment occurred.
