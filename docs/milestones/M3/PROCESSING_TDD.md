# M3 processing and persistence TDD evidence

Date: 2026-10-20. Scope: SRS-009/011/012/013/014/015/016/048/049/050, shared SRS-041/055. Synthetic fixtures and real temporary SQLite only. No ALM/model network calls, downloads, active revision changes, generation creation, or index writes.

## Actual Red

Before `processing.py` and migration 004 existed, the initial eight processing tests were written and run with:

```sh
PYTHONPATH=src /Users/skongby/projects/alm-rag/.venv/bin/python -m pytest -q tests/test_processing.py
```

Observed: collection failed with `ModuleNotFoundError: No module named 'almrag.processing'`. This was a real import-stage Red; it is not claimed to be eight executed behavioral assertion failures. The first implementation then executed eight tests with seven failures and one pass; the SQLite content block INSERT had nine placeholders for eight columns. Correcting the INSERT produced eight passes.

Two later actual behavioral Reds were observed before their corrections:

- `test_processor_version_drift_blocks_pinned_job`: changing the normalizer version after enqueue unexpectedly returned `SUCCEEDED` instead of `BLOCKED`. Processor versions now live in the hashed immutable job snapshot and runtime refuses a version drift.
- `test_processing_schema_rejects_cross_revision_membership`: SQLite accepted another revision's chunk in a processing result. Migration 004 now enforces result/project/revision, membership, outcome and vector ownership; cross-revision membership raises `IntegrityError`.

## Green and regression

Final command:

```sh
PYTHONPATH=src /Users/skongby/projects/alm-rag/.venv/bin/python -m pytest -q tests/test_processing.py tests/test_collection.py tests/test_storage.py tests/test_queue.py
```

Observed: **57 passed in 7.32s**, including **19 processing tests**. PASS is limited to these executed synthetic tests. Coverage includes:

- Typed normalized/source field IDs, instance/project/scope inheritance, distinct missing-field failure, opaque structured values rejected Item-locally, complete original envelopes retained.
- Immutable pinned source revisions, typed effective policy, processor versions and runtime profile fingerprint; stale configuration cannot silently alter a queued job.
- Namespace-safe same-revision reprocessing under field/config/model changes; project-local vector cache and revision-owned chunks.
- Identical reruns and metadata-only revisions produce zero new content embedding calls; selected-field addition and changed descriptions embed only newly changed exact inputs. Changed prefix and model use separate cache entries.
- A 15,000-character synthetic description yields more than 100 complete chunks bounded to the verified fixture profile's 128-token context, even though the policy default is 1024. The codepoint tokenizer is explicitly fixture-only and not production token evidence.
- Finite vector/dimension/digest validation, corrupted cached vectors stop globally, model drift blocks all derived writes, and model `PAUSED` state/error code survives orchestration.
- Per-Item model input rejection continues siblings and records failed Item revision/stage; no partial Item result becomes `EMBED_READY`.
- Expired owner cannot write vectors/outcomes/counters. A partial vector cache survives lease recovery; the result remains `PROCESS_READY` until all chunks are verified, then the remaining content input alone is embedded. Runtime abort callback is restored afterward.
- Active revision/generation/index structures remain untouched.

## Service and persistence contracts

`ProcessingService(db, runtime_factory, allow_fixture=False)` exposes `configure`, `configure_instance`, `get_config`, `preflight`, `enqueue` and `run`. Policy JSON accepts only typed fields/scope overrides/chunk configuration; it has no way to grant verified runtime state. Production rejects fixture profiles. Runtime construction/calibration errors propagate their stable code; unconfigured profile prevents queue submission. PROCESS and EMBED each own terminal queue completion and all writes share the fencing guard's SQLite transaction.

`preflight` reports `status`, `process_ready`, `embed_ready`, `sync_ready=False`, `estimated_items`, full snapshot `config_revision` and `diagnostics`. EMBED requires matching prepared results for the pinned latest source revisions and effective policy; otherwise submission raises `PROCESS_REQUIRED`. `get_config.config_revision` identifies local policy state; the full preflight revision additionally pins source revisions and runtime/processor configuration.

Migration 004 adds `processing_instance_policies`, `processing_project_policies`, `processing_snapshots`, `processing_results`, `processing_membership`, `processing_outcomes`, `embedding_cache`, `embedding_manifests`, `embedding_chunk_vectors`. Processing result states are `PROCESS_READY` and `EMBED_READY`. Existing content block/chunk rows use result/config namespaces; cache identities remain independent of revision UID.

Real Ollama digest/context calibration, exact production tokenizer behavior, live ALM processing and M4 index activation: **NOT VERIFIED / not executed**. No synthetic evidence changes those statuses.
