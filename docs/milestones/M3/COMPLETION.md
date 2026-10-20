# M3 completion — approved with documented limitations

2026-10-20; branch codex/m3-content, based on approved M2 commit0b38393. Status **APPROVED_WITH_DOCUMENTED_LIMITATIONS** by user “진행해” after delivery of4232f7a and its approval request. M4 separately authorized; original completion measurements and limitations below remain unchanged.

M3 now prepares revision-owned text/table chunks, stores processing policy/input snapshots, and embeds only changed complete inputs into a project-scoped vector cache. Field selection inherits instance→project→Tracker/Type defaults with distinct normalized/source IDs. PROCESS/EMBED are available through existing authenticated API/CLI/worker; source raw data remains complete, and active revisions/indexes remain untouched. Current contract/type client/negative ACL tests and migration004 are included. No M5 wizard dependency.

| Result | Actual evidence |
|---|---|
| PASS | Main271Python tests33.68s; independent QA271tests33.18s; Frontend8tests and TypeScript/Vite build |
| PASS | Mock E2E4tests:15k-token paragraph+100data-row merged table/oversized cell/full char-UTF8-cell coverage; unchanged rerun0embedding calls;100Items/3parser failures→97ready and all100raw retained; pinned local tokenizer regression |
| PASS | OI-046 parser fatal-resource loss and OI-047 artifact truncation/padding corrections independently retested; no confirmed remaining Critical/Major |
| PASS | Frozen locks; package build/offline wheel migration install1..4; Python/Node audits0; current M3 API/client parity; static docs/diff checks;10Primary+7Shared trace rows |
| PASS | API/Worker imagebf5b8fb5796d,Frontend1b5c02aef5c0;3healthy nonroot containers/schema1..4/proxy; network-none M3runtime55chunks/13content requests/repeat0, M2regression39GET |
| FAIL / retained environment limitation | Bare Python3.9.6 lacks tomllib; project .venv Python3.12 static validation passes. Global Node25 remains broken; use Node22 |
| NOT VERIFIED | Actual Ollama/model/tokenizer/context/vector quality; actual ALM/wiki safety/deletion/TLS; remote CI; hard process kill during real-model I/O; other-platform/OS image scans/shared filesystem; active Item search/detail/publication/Qdrant/replay/M4 |

All model evidence is synthetic **FIXTURE_ONLY**. No model weights/tokenizer artifact were downloaded; production model access stays disabled by default. Missing/unverified runtime blocks PROCESS/EMBED safely. Accepting this local candidate does not establish actual deployed-model token safety or retrieval quality. Unsupported nested/group-scope/ambiguous tables fail Item-locally; a general fallback is not claimed. Original HTML remains authoritative in immutable source envelopes; normalized spans are not raw HTML byte offsets.

Detailed evidence: TEST_REPORT.md, QA_REPORT.md, GATE_MATRIX.md, M3_TRACEABILITY.csv, RUNBOOK.md and actual TDD records. AC-02/03/05/10/12 have M4 index/search/active-detail/replay portions; only their M3 source/chunk/cache subsets passed here. Legacy original REQ clauses remain NOT VERIFIED. Historical M2 initial-prototype TDD_NOT_EVIDENCED accepted exception remains recorded, never retroactive PASS.

Test containers are stopped with volumes retained. No live ALM/model call, remote Push, Notion transmission, destructive DB operation or production deployment occurred. Local candidate commit is reported in Git/final response, outside the commit itself. M3 approval recorded in BASELINE_APPROVAL.md; no M4 implementation is part of this historical candidate.
