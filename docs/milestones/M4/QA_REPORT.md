# M4 independent QA checkpoint — FAIL

2026-10-20. Core QA role, read-only; implementation stopped on confirmed unresolved Major OI-049. This is not M4 completion approval.

## Confirmed Major: SRS-018 exact Item ID retrieval missing

Independent synthetic reproduction: source_item_id=ALM-EXACT-987654, title=Brake torque requirement, description=Torque limits. PROCESS/EMBED and INDEX publication completed. LexicalIndex.search(project,generation,'ALM-EXACT-987654',10) returned []. Chunk inputs contain title/field/body only, and no exact source-ID channel is present. SearchRequest fields are query/project_uids/top_k/response; filters.source_item_id is rejected extra_forbidden. SRS.md:39 requires exact Item ID and filter search. The draft schema also omits it, so schema agreement cannot establish acceptance.

Independent command actually executed:

```
.venv/bin/pytest -q tests/test_indexing.py tests/test_retrieval.py tests/test_readers.py tests/test_pipeline.py tests/test_vector_store.py tests/test_lexical.py tests/test_processing.py tests/test_chunking.py tests/test_normalization.py
```

PASS:166 tests in21.63s. This does not cover the missing requirement. No implementation edits by QA.

NOT VERIFIED by this independent review: actual Qdrant rerun, in-progress API/client integration, complete TEST-044..059 review and full M4 security acceptance. Review stopped on the Major per AGENTS.md. Main's separate local Qdrant measurements are not independent QA results.

See CORRECTION_PROPOSAL.md. Human corrective approval is required before further implementation.

## Final independent correction review — 2026-10-21: PASS within tested scope

User approved OI-049 correction and sequential M4→M5→M6 without further human approval prompts. The original FAIL remains historical. Independent QA reported101focusedPASS8.75s and **417passed64.63s**, actual dedicated localQdrant enabled, exit0/noSKIP. Exactsource/internalIDs, two-projectsameIDscoping, publishedscopefilterconsistency, metadata-onlyzeroChunkoriginalrestoration, typedfiniteJSONfilters, prelimitallowlists, pipeline/readmanageACL and sanitizedaudit checked. No remaining confirmedCritical/Major in boundedcore/APIreview; QA made no implementation edits.

Main separately measured frontend10PASS+build, offlinewheelmigrations1..6, finalimages/threehealthyservices/network-noneM4smoke, static/diff and language package audits. These are not independently rerun QA packaging claims. After final fullQA, certifi advisory was fixed by singlepackage lock upgrade and69HTTP/security/runtime regressionsPASS2.11s plus audit0 and correctedimageboot/smoke. No application behavior changed after final417PASS.

Actual ALM/model/tokenizercalibration/searchquality, remoteCI and otherhostplatforms remain NOT VERIFIED. No M5 UI acceptance is implied by the M4 client build.
