# M6 benchmark harness evidence

Scope: SRS-035 (capacity), SRS-036 (latency measurements), SRS-037 (embedding throughput measurement interface). Owner: isolated `.worktrees/m6-benchmarks`, based on M5 commit `3731374`. No model downloads, actual ALM access, application DB replacement or remote publishing.

## Actual Red / Green

Command run in this worktree:

```sh
/Users/skongby/projects/alm-rag/.venv/bin/pytest -q tests/test_benchmark_m6.py
```

- Red: **3 failed in 0.06s**, `FileNotFoundError` for the two not-yet-created benchmark modules. Tests already specified nearest-rank latency calculation/input rejection; 12-Item canonical multi-chunk publication and owned collection cleanup; embedding changed-ratio/batch/error/token throughput accounting.
- Green after implementation: **3 passed in 0.26s**.
- Refactor: direct fixture FTS insertion instead of `LexicalIndex.put` delete-then-insert, because every synthetic ID is new and repeated deletion by the unindexed FTS point column would introduce quadratic fixture setup costs. This explicitly does **not** benchmark production ingestion.
- Refactor regression: **3 passed in 0.25s**.
- Final regression including exact Qdrant point-count aggregation: **3 passed in 0.21s**.

## Interfaces and bounds

`tools/benchmark_m6.py`:

- `run_benchmark(store, item_count=100000, samples=100, warmups=5)` owns a temporary SQLite directory and one random `almrag_<UUID>` collection. Only that collection is deleted in `finally`. No external SQLite path can be supplied.
- Seeds full canonical Item/revision identities, collection membership, preserved raw envelope, processing result/chunk membership, lexical documents, dense payload/manifests and active publication. Chunk counts cycle 1/2/3 per Item; measured distribution and mean are reported. Fixture setup bypasses collection, processing and model embedding.
- Searches through the actual `SearchService` default hybrid path, one explicit project, compact top 10, single request at a time. Query distribution is exact source IDs using deterministic stride 7919; it exercises exact-ID priority and both dense/keyword backend calls. It is not representative free-text model-quality evidence.
- Reports SQLite bytes/table counts/integrity/foreign-key check, exact remote point count, seed seconds, sample counts, raw measured latency seconds, nearest-rank P50/P95, exact-ID rank-one count, platform/architecture/logical CPUs. P95 ≤3s is reported only as a **synthetic** comparison; actual warm Ollama target remains **NOT VERIFIED**.
- CLI requires `--synthetic-loopback-qdrant`, fixed authorized synthetic loopback endpoint and synthetic test-only key. No actual source/model credentials are read. Only aggregate JSON belongs in Git.

`tools/benchmark_embedding.py`:

- `measure_embedding(embed_batch, texts, token_counter=..., batch_size=..., changed_ratio=..., environment=...)` is an injectable pure harness; it creates no network client.
- Measures successful chunks/s and tokens/s, attempted/successful/failed chunk counts, elapsed seconds, batch size, changed ratio and CPU/GPU/REMOTE/FIXTURE label. Counts failed batches explicitly and validates finite outputs/bounds. Environment labels describe the supplied adapter, and alone provide no actual hardware/model verification.
- No actual CPU/GPU/remote embedding adapter was executed. All three environments remain **NOT VERIFIED**.

## Execution limitation observed by this subagent

The first actual 100,000-Item CLI invocation failed immediately with `VECTOR_TRANSPORT_ERROR` because sandbox loopback transport was unavailable. The escalated retry tool remained in approval wait for 688 seconds and was interrupted; it returned no process/session ID. Consequently this subagent **did not run or claim PASS for the 100k measurement**. No collection was populated by that attempt. The coordinator will execute the reviewed CLI separately and record its actual aggregate output.

Suggested coordinator command after copying the owned files:

```sh
PYTHONPATH=src .venv/bin/python tools/benchmark_m6.py --synthetic-loopback-qdrant --items 100000 --samples 100 --warmups 5 --output docs/milestones/M6/benchmark-100k.json
```

Status: harness unit/SQLite fixture behavior **PASS**; actual 100k capacity and local Qdrant latency measurement **NOT VERIFIED by this subagent**; actual warm Ollama P95 and real model CPU/GPU/remote throughput **NOT VERIFIED**.
