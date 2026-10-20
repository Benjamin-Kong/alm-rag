# M4 Qdrant adapter TDD evidence

Date: 2026-10-20. Isolated worktree: `.worktrees/m4-vector`, base M3.
Owner: rag_engineer. Only `vector_store.py`, `test_vector_store.py`, and this document are owned here.

## Requirements and implementation scope

- SRS-018: dense Qdrant query channel, REST query endpoint.
- SRS-019: exact project and generation filters sent inside the Qdrant query before limit/offset; foreign returned payloads rejected.
- SRS-023/024/033: isolated internal generation collections, verified unnamed Cosine dimensions, waited completed writes, retrieval with exact payload and full vector for the coordinator's SQLite manifest comparison.
- SRS-026/028: lease abort propagation, bounded requests/responses/deadlines, no redirects or environment proxy, default live network disabled, sanitized authentication/transport/server errors.

No publication, active pointers, SQLite schema, API authorization or generation cleanup policy is implemented in this adapter. The coordinator must authorize query projects, compare exact point/vector/payload manifests, and protect generation cleanup with reader pins before calling collection deletion. Missing retrieval IDs remain absent so the caller can reject incomplete coverage. Point IDs are canonical UUID strings. Payloads contain exactly the nine frozen design keys. The client uses fixed internal collection paths; source content never becomes a URL.

## Actual Red / Green observations

Commands below ran from the isolated worktree using `/Users/skongby/projects/alm-rag/.venv/bin/python` (project Python 3.12).

1. `... -m pytest -q tests/test_vector_store.py`: exit 2, missing `almrag.vector_store` at collection; no implementation existed.
2. Added behavior stub with the frozen public method names; same command: exit 1, **28 failed** with `NotImplementedError` (0.21 s).
3. Implemented adapter; same command: exit 0, **28 passed** (0.15 s).
4. Added score overflow, deadline/lease, protected error body, request/batch bounds, and known-dimension cases; same command: exit 1, **1 failed, 32 passed** (0.19 s). A server JSON integer score `10**400` caused `math.isfinite` to raise `OverflowError` rather than the sanitized vector error.
5. Minimal score validation fix catches numeric conversion overflow and raises `VECTOR_RESPONSE_SCHEMA_MISMATCH`; full regression result recorded below.

Final full command: `/Users/skongby/projects/alm-rag/.venv/bin/python -m pytest -q`.
Result: exit 0, **304 passed in 31.76 s** (271 inherited M3 + 33 vector adapter cases).

All HTTP tests use `httpx.MockTransport` with synthetic payloads. Auth errors are rejected without reading protected error bodies; the test stream fails immediately if read. No ALM server, real Qdrant, model server, credentials, customer text or external mutation was used.

## Static baseline observations

- `python3 tools/validate_baseline.py`: exit 1, native interpreter lacks `tomllib` (`ModuleNotFoundError`). This is not reported as PASS.
- `/Users/skongby/projects/alm-rag/.venv/bin/python tools/validate_baseline.py`: exit 0, **DOC_STATIC_PASS**, 50 decisions / 252 legacy mappings / 59 SRS / 6 subagents / 42 draft operations. Static document evidence only.
- `git diff --check`: exit 0, repeated after final documentation edit.

## Official REST references

- [Qdrant query points](https://api.qdrant.tech/api-reference/search/query-points): POST `/collections/{name}/points/query`, filter, limit, offset and result points.
- [Qdrant retrieve points](https://api.qdrant.tech/api-reference/points/get-points): POST retrieval with payload/vector inclusion.
- [Qdrant create collection](https://api.qdrant.tech/api-reference/collections/create-collection): unnamed vector size and distance configuration.

Actual server/version compatibility, network interruption behavior and production authentication/TLS remain **NOT VERIFIED** here. There are no known unresolved Critical/Major defects in this bounded adapter's tested scope; independent QA and integrated index publication remain coordinator responsibilities.
