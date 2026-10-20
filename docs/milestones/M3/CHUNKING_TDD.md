# M3 exact-input chunking TDD evidence

Date: 2026-10-20. Owner: chunk specialist in isolated `.worktrees/m3-chunks`.
Scope: `src/almrag/chunking.py`, `tests/test_chunking.py`, this evidence file only.
Requirements: SRS-011/012/013/014/048/049; approved CHUNKING_POLICY and M3 DESIGN.

## Actual Red → Green

Executed with the main project's existing Python environment, from this worktree:

```sh
PYTHONPATH=src /Users/skongby/projects/alm-rag/.venv/bin/python -m pytest tests/test_chunking.py -q
```

1. Tests were written before implementation. Initial collection failed because `almrag.chunking` did not exist (1 collection error).
2. Added only configuration validation, the public exception and a behavior stub, then ran the same command: **18 failed, 5 passed**. Every behavior failure was the explicit `NotImplementedError` in `make_chunks`, establishing actual behavioral Red rather than relying only on import failure.
3. Implemented exact-input chunking: **22 passed, 1 failed**. The remaining test incorrectly expected more than 20 chunks for a 15,000 synthetic-token cell; the valid output contained 19 complete, bounded chunks. Replaced that arbitrary count with more than 15, retaining exact-input bounds and independent full span/cell coverage assertions.
4. Added source-inventory, empty-cell, duplicate-block and alternate exact-counter regression cases. **27 passed**. Existing regression suite plus these tests: **205 passed in 14.93s**.
5. Added a test for the effect of reserved context on the soft payload target before implementing it: **1 failed, 27 deselected**, because both reservations produced a 340-character first payload. Added actual reservation budgeting; **28 passed**.
6. Added an explicit row-header-only table fixture before support: **1 failed, 28 deselected** (`AMBIGUOUS_TABLE_HEADERS`). Allowed validated explicit row-header associations without inventing column headers; **29 passed in 0.10s**.

Final complete regression command: `PYTHONPATH=src /Users/skongby/projects/alm-rag/.venv/bin/python -m pytest -q`. Actual result: **207 passed in 14.24s** (178 existing tests plus 29 chunking tests).

## Verified behavior

- Synthetic exact token fixtures cover 100 / 1,024 / 8,000 / 15,000 Unicode token sources, long unbroken sentences, a 15,000-token table cell and alternate UTF-8-byte vocabulary. These vocabulary definitions are explicit fixture tokenizers, not estimates for a real model.
- Exact final inputs include prefix, title, field identifier, section headings, repeated table header hierarchies, row/cell identities and values. Every emitted input is counted by the injected tokenizer and checked against `min(max_chunk_tokens, effective_max_input_tokens - safety_margin)`.
- Semantic paragraph/sentence boundaries precede bounded character subspans. Original normalized whitespace remains in source spans. Description overlap applies only to the typed `normalized:description` field; source fields named description do not receive overlap.
- Normalized block/cell character and UTF-8 byte ranges reconstruct all source text. Independent `source_inventory`, when supplied, must equal source block/cell bodies; final span unions must cover every unit. Empty cells retain their identities.
- Table grids, original cell counts, spans and header identities are checked. Multirow headers repeat; each rowspan origin is serialized once with its complete row/column grid relationship. Oversized rows split cell values while repeating header relations. Truly headerless, missing-cell, conflicting-grid and invalid-header tables fail Item-locally.
- Context/header/atomic association that cannot fit raises `ChunkingError` with a code and `global_error=False`; it never drops content or silently truncates.
- Exact input, model fingerprint, tokenizer identity, all configuration fields, normalizer version, chunker version and table serialization version contribute to the content hash. Revision UID and cosmetic raw HTML do not. Chunk identity also distinguishes normalized source spans and typed field ownership.

## Consumer contract check

Loaded the normalization specialist's module directly from its isolated worktree using `importlib`, without copying or editing its files. Normalized its synthetic `complex_table.html`, then passed the resulting document including independent source inventory into this chunker.

Actual result: **PASS**, 4 blocks, 13 source units, 4 chunks, maximum exact input 502 synthetic tokens. This covers multilevel column headers, explicit row headers, row/column spans and distinct repeated cell values across the specialist module boundary.

## Not verified / boundaries

Real Ollama model/tokenizer calibration, effective model context, truncation behavior, runtime vectors, full Item SQLite restoration and indexing are outside this module's unit evidence. No model artifacts or networks were used. An injected counter is a capability contract; production verification must be established independently by the runtime gate. This work does not switch active Item revisions or index generations.
