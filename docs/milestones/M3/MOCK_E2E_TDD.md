# M3 service mock E2E evidence

Date: 2026-10-20. Scope: SRS-011/013/014/015/016/048/049/055. Owned changes are only `tests/test_m3_mock_e2e.py` and this evidence file. Application implementation is the coordinator's current integrated M3 code, copied read-only into the isolated test worktree.

## Actual chronology

These tests extend coverage of an already implemented service pipeline. They do not establish a feature-first Red for that earlier implementation.

1. Wrote two tests that submit authenticated HTTP API requests, enqueue real jobs, run the real worker and collection/processing services, use the shared mock ALM HTTP transport, use the actual `OllamaEmbedder` against mock HTTP, and inspect real temporary SQLite rows.
2. First command `PYTHONPATH=src /Users/skongby/projects/alm-rag/.venv/bin/python -m pytest -q tests/test_m3_mock_e2e.py` observed **2 failed in 1.72s**. Both failures were incorrect test assumptions, not application defects: repeated synthetic chunks produced only six distinct content embedding requests because the cache deduplicated them; the public job response does not expose `progress_total`.
3. The independent QA OI-047 Major tokenizer finding triggered the project stop gate. The tests were preserved unfinished, no application changes were made by this agent, and no PASS was claimed.
4. After the user's continuation authorization, seeded the coordinator's current runtime including its OI-047 fix. Corrected the first assertion to check persisted chunk count independently of unique embedding request count. Read durable counters from `Queue.get_job`, while still checking the job's state through the API. The two tests then observed **2 passed in 2.06s**.
5. Added a third integration regression using actual `LocalTokenizer` with a locally generated synthetic WordLevel tokenizer artifact containing saved truncation and padding settings. An independent unconfigured WordLevel reference supplies mock Ollama's expected token counts. The test passed on its first run against the existing fixed implementation. This is regression/integration evidence, not a new Red/Green cycle for OI-047.

## Final executed command

```sh
PYTHONPATH=src /Users/skongby/projects/alm-rag/.venv/bin/python -m pytest -q tests/test_m3_mock_e2e.py
```

Observed: **3 passed in 2.85s**.

## Verified boundaries

- **Full service path:** session/CSRF authenticated API → durable SQLite queue → real worker → collection and processing services → actual embedding client with mock HTTP → persisted blocks, revision-owned chunks, cache, chunk-vector memberships and manifest.
- **Merged table and oversized input:** a 15,000-token paragraph under the explicitly named codepoint fixture tokenizer and an 8,000-character cell, plus colspan/rowspan header associations. The test independently checks full character/UTF-8 span union coverage of the paragraph and every normalized table cell. More than 20 persisted chunks obey the exact complete-input 1024-token bound. The original raw HTML and opaque unselected custom field survive collection unchanged.
- **Selective embedding:** calibration requests are distinguished from content requests. All mock `/api/embed` requests use `truncate:false`. Identical PROCESS/EMBED reruns add zero embedding requests, including calibration requests, while retaining complete vector memberships and manifest counts. Processing makes no ALM HTTP calls; collection's source calls are GET only.
- **Item-local normalization failure:** a nested table records `TABLE_NESTED_UNSUPPORTED` against its actual source revision. The job reaches `COMPLETED_WITH_ERRORS` with total/success/failure counters 2/1/1, the valid sibling produces its chunk, and the malformed original HTML remains complete in immutable storage.
- **Real local artifact regression:** the saved tokenizer artifact truncates to 2 tokens and pads to 64 when read directly by the tokenizer library. `LocalTokenizer` counts all 200 synthetic words and counts a one-word input as 1. Through the actual processing/embedding clients, every chunk's stored count matches an independent reference tokenizer and stays within the runtime's 128-token bound. Repeated runs reuse vectors without additional embedding calls.
- **No activation:** the service tests leave active revisions and index generations untouched.

All tokenizers, source data, credentials, vectors and model responses are synthetic. Runtime evidence remains `FIXTURE_ONLY`, including the real local artifact test because the model HTTP transport is mocked. Production Ollama compatibility/calibration, model weights, live ALM, deployment, and M4 index/search behavior are **NOT VERIFIED / not executed**. No network traffic, downloads or remote writes were performed by these tests.

## Final acceptance coverage extension in Main

Before final handoff, the specialist extended the existing large-Item fixture to100data rows (plus2header rows), retaining the merged cells and8k-character cell. A fourth actual API→COLLECT→PROCESS test adds100Items, with three nested-table parser failures: durable counters100/97/3/0, all100original envelopes retained,97PROCESS_READY results,3actual-revision failed-items, no active/index mutation. Specialist execution was interrupted by its runtime usage limit after the edits; no execution claim was inferred. Main copied only the owned test/evidence files and actually ran `.venv/bin/pytest -q tests/test_m3_mock_e2e.py`: **4PASS9.68s**. No application implementation changes were required.

These local stage tests cover the M3 subset of AC-10/AC-12. Actual model context verification, full SYNC, active Item detail/search restoration and public per-Item replay remain NOT VERIFIED/later milestone work. The100/3test proves parser isolation; embedding-local failures are separately tested in test_processing.py and are not falsely described as the same100-item run.
