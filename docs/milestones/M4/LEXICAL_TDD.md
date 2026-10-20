# M4 lexical channel — executed evidence

Scope: SRS-018/019. Synthetic local SQLite only; isolated worktree `.worktrees/m4-lexical`. Ownership: `src/almrag/lexical.py`, `tests/test_lexical.py`, this report. No shared migration, live service, source body, active pointer or root application edits.

## Red → Green

2026-10-20: wrote the initial 13 parameterized test cases before creating `almrag.lexical`.

Command: `/Users/skongby/projects/alm-rag/.venv/bin/python -m pytest -q tests/test_lexical.py`

- Red: exit 2; collection failed with `ModuleNotFoundError: No module named 'almrag.lexical'`.
- Implemented the bounded module. Same command: **13 passed in 0.08s**, exit 0.
- Added regression verification for an insertion failure caught inside the caller transaction and BM25 document-length/NFKC behavior. **15 passed in 0.22s**, exit 0. These two additional checks were first run after implementation; no separate Red is claimed.
- Added the 1,024-term accepted query boundary, matching its final term. Final targeted command: **16 passed in 0.24s**, exit 0. This boundary check was first run after implementation; no separate Red is claimed.

Full isolated regression started with the 15-test file: `/Users/skongby/projects/alm-rag/.venv/bin/python -m pytest -q` → **286 passed in 31.78s**, exit 0. The sixteenth lexical boundary check was added while that already-collected run was executing and was verified by the final separate 16-test run; the full run does not claim 287 tests.

## Verified behavior

- `nfkc-casefold-hangul23-identifier-hex-v1` preserves exact NFKC/casefold automotive identifiers (`SOME/IP-SD`, `30490`, hexadecimal values) and their components. Hangul whole terms and lengths 2/3 substrings are emitted. Distinct tokens are stored once per document; this initial version uses binary token frequency, with FTS5 BM25 document-length/IDF scoring. Future frequency/segmentation changes require a new version and rebuild.
- UTF-8 hex token encoding prevents unicode61 from splitting punctuation and prevents embedded FTS grammar from executing. Query tokens become parameterized quoted OR operands.
- Both exact project/generation predicates are evaluated inside SQL before LIMIT/OFFSET. Ties use point ID. Only the five allowed identity payload properties are returned.
- Replace is idempotent, and both document/FTS writes are protected by a savepoint inside the mandatory caller-owned transaction. Failed replacement remains atomic even if caller catches its exception. Generation deletion participates in the caller transaction.
- Query complexity is rejected explicitly above 65,536 characters or 1,024 distinct generated terms. Limits 1..1,000 and offsets 0..1,000,000 are validated; booleans are rejected. No partial token list is silently searched.

Synthetic comparison: the body `차량속도감지 SOME/IP-SD 30490 0xAB12` returns zero matches for `속도` under bare unicode61; versioned pretokenization returns the expected point. Both return the numeric identifier. Exact identifier/component queries and mixed-width forms pass. This is a fixture comparison only: no Korean morphological-analysis, representative recall, latency, or production corpus quality claim.

## Other actual checks

- `python3 tools/validate_baseline.py`: failed because system Python lacks `tomllib` (environment interpreter mismatch).
- Re-ran with project Python: `/Users/skongby/projects/alm-rag/.venv/bin/python tools/validate_baseline.py` → **DOC_STATIC_PASS** (50 decisions, 252 legacy rows, 59 SRS, six subagents, 42 draft operations). Static document evidence only.
- `git diff --check`: exit 0.

NOT VERIFIED: main migration/API/retrieval integration, live ALM, Qdrant/model, production keyword relevance, M6 corpus/latency targets. Main coordinator owns those integration gates.
