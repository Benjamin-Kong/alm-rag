# M3 content processing plan

Status: PENDING_APPROVAL_WITH_DOCUMENTED_LIMITATIONS — local/mock acceptance and independent QA complete, real model/ALM and later-stage acceptance NOT VERIFIED. See docs/milestones/M3/COMPLETION.md. Original M3 start2026-10-20 on codex/m3-content; M4 not started.

Primary10: SRS-009/011/012/013/014/015/016/048/049/050. Shared7: SRS-010/017/039/041/055/058/059. Assignments unchanged; preserve legacy clause NOT VERIFIED.

## Sequence and ownership

1. Coordinator reads source specs, records this plan/design and approval; architect reviews contracts read-only. No implementation before actual failing tests.
2. RAG normalization specialist owns src/almrag/normalization.py, tests/test_normalization.py, synthetic tests/fixtures/content/** and NORMALIZATION_TDD.md in isolated .worktrees/m3-normalize. No shared file writer.
3. Chunk specialist owns src/almrag/chunking.py, tests/test_chunking.py and CHUNKING_TDD.md in isolated .worktrees/m3-chunks. Consumes dict normalization contract and injected exact token counter, not another specialist's mutable implementation.
4. Main owns embedding runtime/client/manifest, additive migrations, processing policy/snapshots/cache/persistence, worker/API/CLI/OpenAPI/client, integration tests/docs. Main never switches active revision/generation or indexes in M3.
5. Independent QA read-only after integration; three bounded correction rounds maximum, immediate Critical/Major Human Gate. Test evidence, Primary/Shared traceability and TEST-044..059 assessment precede M3 approval request.

## Acceptance focus

Actual Red→Green for merged/nested-invalid table handling, block order/headers/provenance, selected per-scope fields,15k-token synthetic Item and oversized table cell, exact-input token limits, complete normalized span/cell coverage, no truncation. Repeat identical input makes zero embedding calls; changed fields/model/tokenizer/config invalidate correct cache entries. Worker fencing/crash/restart and Item-local errors preserve existing active content.

## Preflight limits

Native M2 runtime and178 Python tests passed before this milestone. Local ollama CLI, lxml, tokenizers and sentencepiece are absent at M3 start. Approved development dependencies may be installed and locked; no model weights are downloaded automatically. Real Ollama digest/context/tokenizer calibration is NOT VERIFIED. Production EMBED stays BLOCKED without matched verified runtime evidence; fixture tokenizers/embedders are explicitly mock-only. No character/byte heuristic is declared a safe real-model token count.


## Actual integration ownership supplement

Main delegated processing.py, migration004, test_processing.py and PROCESSING_TDD.md to m3_pipeline in isolated .worktrees/m3-pipeline; copied only those frozen owned outputs into Main after its actual19test/57regression handoff. Main retained all embedding/runtime/API/CLI/Worker/OpenAPI/client/integration/packaging/doc ownership. The same specialist later owned only test_m3_mock_e2e.py and MOCK_E2E_TDD.md in that worktree; final four cases were executed in Main after its agent runtime limit interrupted the last handoff. QA agents were read-only and source/test writers never edited the same files concurrently. No M4 implementation.
