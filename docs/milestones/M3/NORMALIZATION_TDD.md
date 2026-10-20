# M3 normalization test evidence

Date: 2026-10-20. Scope: synthetic, local field normalization only. SRS-011/016/049/050 (partial TEST-011/016/049/050 evidence); no milestone approval implied.

## Executed Red → Green

Worktree: `.worktrees/m3-normalize`. Commands used the main shared Python environment with worktree source isolation:

```sh
PYTHONPATH=src /Users/skongby/projects/alm-rag/.venv/bin/python -m pytest tests/test_normalization.py -q
```

1. Before implementation: exit 2, one collection error, `ModuleNotFoundError: No module named 'almrag.normalization'` (0.09s). Tests and synthetic HTML fixture existed before the implementation module.
2. First implementation: 11 passed, 2 failed (0.82s). Both failures were test expectations: source fixture contains 10, not 11 cells; optional closing HTML tags are valid and do not necessarily produce parser recovery diagnostics. Corrected the count and used an actual unexpected closing tag for the recovery test. These corrections are not represented as implementation fixes.
3. First Green: 13 passed (0.04s).
4. Additional integrity tests before corrective code: 15 passed, 4 failed (0.07s). Observed failures: adjacent block text inside cells concatenated words; stray visible table/row text was silently omitted; a blank required header was accepted.
5. Minimal correction: preserve separators at cell paragraph boundaries; reject non-whitespace table text outside cells/captions; reject blank headers used by data cells. Green: 19 passed (0.04s).
6. Full worktree regression: `PYTHONPATH=src /Users/skongby/projects/alm-rag/.venv/bin/python -m pytest -q` → 197 passed (14.66s), including 178 pre-existing tests. `git diff --check` → exit 0.
7. `.venv/bin/python tools/validate_baseline.py` (absolute shared Python used) → `DOC_STATIC_PASS`; this is specification-file evidence only.

## Observed behavior

- Mixed wrapper text/tail, headings, paragraphs, lists and tables retain order. Embedding text excludes cosmetic markup, comments and script/style content; meaningful link text remains. No resource retrieval or execution occurs.
- Unicode character and UTF-8 byte spans explicitly describe normalized block/cell text. DOM paths identify provenance; no exact raw-HTML byte offsets are claimed. Per-block/cell `raw_html` is DOM serialization, which may repair source markup. The immutable collection envelope remains the authority for original field bytes.
- Table JSON stores distinct source cell IDs, coordinates, rowspan/colspan, occupancy grid, raw fragments, header rows, caption and explicit `header_ids`. Repeated identical text cells remain distinct.
- `source_inventory` is captured independently before derived block/cell structures are constructed. Output cell identities are compared against the source DOM inventory. Mutating/removing derived blocks or cells does not mutate the inventory.
- Malformed overlap, out-of-range spans, incomplete grids, nested tables, unresolved/cyclic headers, unsupported scope groups, or uncertain source text fail with `NormalizationError(code)` and `global_error=False`. No unlabeled flattening or invented column names.
- Limited HTML parser recovery is accepted only when the resulting complete table grid and associations validate; parser-reported repairs carry `HTML_RECOVERED`.
- `Html`/`Wiki` format aliases are case-insensitive. Unrendered Wiki remains literal text with `WIKI_UNRENDERED`. Scalars normalize deterministically; unsupported opaque structured values, including raw `TableFieldValue` mappings, fail rather than embedding JSON.

## Limits / NOT VERIFIED

Live Codebeamer/Polarion variants, verified source Wiki rendering, actual model/tokenizer/Ollama behavior, retrieval quality and publication safety are not exercised by these tests. Nested tables and `rowgroup`/`colgroup` scopes intentionally fail locally; a validated general fallback is not implemented. Full original byte retention depends on M2 envelopes and coordinator persistence integration. This module alone does not establish complete TEST-049 or TEST-050 acceptance, perform embedding, touch active pointers, index Qdrant, or approve M3.
