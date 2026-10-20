# M2 collection persistence TDD evidence

Owner: collection specialist, isolated `.worktrees/m2-collection`. Synthetic fixtures only; no network, ALM access, remote publication or milestone approval. Main integrates these files explicitly. Date: 2026-10-20 Asia/Seoul.

## Commands and observed results

Run from this worktree with Main's installed runtime:

`PYTHONPATH=src /Users/skongby/projects/alm-rag/.venv/bin/python -m pytest -q tests/test_collection.py`

1. Initial Red before adding collection.py: exit2, `ModuleNotFoundError: No module named 'almrag.collection'` (also rerun with explicit PYTHONPATH). Nine SRS-linked contract tests had been written first.
2. Initial Green after minimal collection service and002 migration:9 passed in1.17s.
3. Hardening Red:2 failed,11 passed in1.44s. A disk-space error was incorrectly isolated; connector transport callback did not guard an expired lease. Green after fixing global storage classification and scoped transport lease callback:13 passed in1.39s.
4. Added regression contracts for stale leases on failure, complete item rollback, missing fields/scopes, Polarion identity and global PAUSED retention:18 passed in1.55s.
5. Attachment integrity Red:2 failed,18 passed in1.82s. Changed attachment bytes under unchanged metadata were not included in revision content fingerprints. Green after including downloaded checksums and checksum-specific attachment identity:20 passed in1.65s.

Full regression command: `PYTHONPATH=src /Users/skongby/projects/alm-rag/.venv/bin/python -m pytest -q`. Initial full regression before final attachment hardening:56 passed in5.14s; one upstream Starlette/httpx deprecation warning. Final full regression after attachment hardening:58 passed in5.20s, same upstream warning. `git diff --check` passed.

## Requirement coverage

| Requirement / baseline test | Implemented evidence |
| --- | --- |
| SRS-003/045/046/047, TEST-003/045/046/047 | Discover project IDs and source-specific scopes; ALL expansion; validate SELECTED membership and fields; readiness distinguishes COLLECT from unavailable full SYNC; stale preflight rejection and transactionally pinned configuration. |
| SRS-004/005/010/022/049, TEST-004/005/010/022/049 | Complete normalized envelope with unprojected raw payload, raw wiki+HTML, typed fields, relations and attachment metadata in immutable revision; attachments downloaded only through adapter to internal checksum paths; original filenames retained only as metadata. |
| SRS-006/007, TEST-006/007 | Identical source revisions/content are reused; changed content under the same original revision blocks globally. No-source-revision observations use explicit observed:hash labels while original revision stays None in raw envelope. Content fingerprints include attachment bytes. Conservative complete enumeration detects changes without trusting modified timestamps. |
| SRS-008/023, TEST-008/023 | Missing/403/out-of-scope are separate membership observations; only deleted=True plus deletion_evidence establishes deletion. Existing raw history and active_revision_uid are preserved. Search exclusion remains M4. |
| SRS-055, TEST-055 |100 references with3 local failures yields97 succeeded+3 failed and COMPLETED_WITH_ERRORS. Pre-revision failure rows contain NULL revision; auth/global/circuit/storage/integrity failures stop globally and retain prior outcomes. |
| SRS-026/055/058, TEST-026/055/058 | Guard outcome, revision, failure, membership, checkpoint and counter writes within their own transactions using the exact current Queue fencing token. Late results/failures cannot commit. Transport abort callback checks lease between requests/waits. Complete refs are persisted once; restart resumes without duplicate outcomes or counters. |

## Integration contract

Owned files: src/almrag/collection.py, src/almrag/migrations/002_collection.sql, tests/test_collection.py, this document. No other files modified; no commits created by this specialist.

CollectionService(db, connector_factory, attachment_root) exposes configure_project, preflight, enqueue and run. run accepts a claimed RUNNING COLLECT job and owns Queue.finish; Main worker must only maintain heartbeat and avoid a second finish. LeaseLost propagates. Adapter.client.abort_check is bound during run and restored in finally. Main owns ordered migration loading, shared transport, adapters, worker integration, APIs, ACLs and type-safe client.

002 adds connection_profiles, collection_configs, collection_snapshots, collection_outcomes, collection_failures, collection_memberships and item_collection_state. item_collection_state.latest_revision_uid is observation-only; active_revision_uid is never updated. Failure/outcome primary keys(job_id,source_item_id) protect per-run idempotence; complete refs pinned after successful enumeration prevent restart drift. Collection snapshots pin config/scope; later local edits do not alter queued scope.

The worktree starts with M1's version1-only runner. Tests explicitly execute002 after Database.migrate when its tables are absent. Main owns upgrading the migration runner; these tests also work when Main runs002 natively.

## Limits / NOT VERIFIED

Real servers, real renderer side effects, production permissions/rate limits, cross-process worker heartbeat and Main API/worker integration are not exercised by these unit tests. Public failure-list/replay API remains deferred under OI-029. Automatic cleanup of unreferenced attachment files after process crashes is not implemented: atomic filesystem writes precede metadata transactions, so rollback/crash may leave safe internal files without DB references. Existing referenced files and metadata are retained. Request estimates exclude unknown attachment counts and page multiplication. No processing, embeddings, indexing, search publication or full SYNC readiness is claimed.
