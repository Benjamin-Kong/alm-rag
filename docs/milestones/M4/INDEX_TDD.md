# M4 index publication — executed TDD evidence

2026-10-20. SRS-020/021/024 and Shared SRS-023/041/049/055. Isolated `.worktrees/m4-index`, ownership only `indexing.py`, `test_indexing.py`, this report. Main-owned schema005/readers/lexical were copied read-only; no schema changes requested or made. Tests use actual SQLite/FTS/ReaderRegistry and the M3 explicitly synthetic fixture runtime plus an in-memory vector store; no network.

Commands below used `/Users/skongby/projects/alm-rag/.venv/bin/python -m pytest -q tests/test_indexing.py`.

## Actual Red → Green observations

- Initial seven contract tests before module: exit2 `ModuleNotFoundError: almrag.indexing`.
- First implementation: 6 PASS/1 FAIL; failed inactive rebuild collection not eligible for cleanup. Marked inactive failed generations FAILED/PENDING. Next run **7 PASS/1.29s**.
- Added four recovery/coverage checks: **2 FAIL/9 PASS** for crash after atomic rebuild publication and lexical deletion between staging/publication. Re-stage idempotently on reclaimed REBUILD and revalidate document/FTS coverage under final SQLite publication transaction. **11 PASS/1.88s**.
- Added model/remote payload drift after staging: **2 FAIL/11 PASS**. Rechecked runtime fingerprint and exact dense readback immediately before publication; complete rebuild repeats checks for all artifacts before the switch. **13 PASS/2.16s**.
- Added blocked-job resume and expired-cleanup fence: **1 FAIL/14 PASS**. Same pinned generation can resume from PENDING before cleanup; ACTIVE reset happens atomically under job fence; DELETING/DELETED refuses resurrection. **15 PASS/2.45s**.
- Empty generation/no-resurrection first execution: **16 PASS/2.71s** (new verification check first run after implementation; no separate Red claimed).
- Added repeated resume after actual GC: **1 FAIL/16 PASS**. Failure cleanup had inadvertently reset DELETED to PENDING. Preserve DELETING/DELETED states in error handling. **17 PASS/2.74s**.
- Added in-flight GC callback fencing: **1 FAIL/17 PASS**. Bind/restore the vector adapter's abort callback while deleting with a supplied running job. Final result recorded below.

## Implemented and verified contract

Stable config fingerprint contains effective field/chunk policy, verified-or-explicit-fixture model profile fingerprint, processor versions and lexical version; it excludes source revision refs. Changed INDEX config requires REBUILD. Immutable job snapshot pins revisions/config and deterministic generation/point IDs. `collection_name_for` and `normalized_vector` are exported for Main integration.

Dense vectors are checked against M3 membership/manifests/cache digests, normalized to unit L2 then float32, uploaded, and read back with exact point/payload identity and finite component tolerance1e-5. Payload vector digest describes the expected normalized float32 vector. No content embedding occurs during indexing.

Both keyword documents and FTS rows are checked before publication; complete manifest/cache/point identity is checked again under the final write transaction. INDEX publishes successful Items independently; a local missing embedding keeps that Item's old active revision and records actual failed revision/stage INDEX while siblings proceed. Global integrity, model, vector and SQLite failures block.

REBUILD stages a distinct generation and publishes every target manifest, active Item revision and the project generation in one fenced SQLite transaction. Any unready/new/stale Item prevents the complete switch. Existing active MISSING Items remain expected coverage: unknown absence cannot silently delete old active content or mix incompatible vectors. Out-of-scope input cannot activate. Sources and immutable original revisions are preserved.

Crash before publication leaves no active revision; reclaim uses the same generation/point IDs. Crash after atomic rebuild publication can be reclaimed without duplicate publication. Job lease loss during upload or cleanup forbids local publication; vector callbacks preserve the lease exception and are restored afterwards. Old generations retire to pending cleanup; actual live-reader OS lock pins defer external/FTS cleanup. After GC, the same job cannot resurrect that generation, including repeated resume attempts; a fresh job is required.

## Regression and limitations

An earlier full isolated run collected the first15 index tests and passed **286 tests/35.93s**. Later added checks are recorded by targeted and final full results below; never infer unrun counts.

Project Python `tools/validate_baseline.py`: DOC_STATIC_PASS (50 decisions,252 legacy mappings,59 SRS,six subagents,42 draft operations), static evidence only. `git diff --check` exit0.

NOT VERIFIED here: Main retrieval/API/CLI/replay/SYNC integration, real Qdrant/model behavior, container execution, live ALM, production concurrency/filesystem and quality/latency targets. Main owns those integration and Human Gates. The memory store cannot establish real Qdrant guarantees or arbitrary external-writer atomicity.

Final targeted: **18 passed in2.91s**, exit0. Final full isolated regression after the last implementation change: `/Users/skongby/projects/alm-rag/.venv/bin/python -m pytest -q` → **289 passed in36.11s**, exit0. Final DOC_STATIC_PASS and diff check repeated successfully. The full289 comprises baseline271 plus all18 indexing tests; lexical/readers dependencies are Main-owned copied modules without their separate test files in this isolated checkout.
