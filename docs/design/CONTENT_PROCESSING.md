# HTML / Table / Chunk Processing Design (Draft)

1. Save raw source (Wiki/HTML/field type) and ALM-rendered HTML when available, with checksum and provenance.
2. Parse HTML DOM with lxml/BeautifulSoup; sanitize only at UI rendering boundary while preserving original separately.
3. Create ordered blocks (paragraph, heading, list, table) with field IDs and block offsets.
4. For tables, build loss-aware structure: table title, header hierarchy, cell order, coords, rowspan, colspan, raw fragment. If normalization loses associations, use validated fallback, else mark FAILED and hold item publication.
5. Normalized **embedding text** removes cosmetic HTML tags/styles but retains meaningful heading/label text. A table converts to repeated `Header = Value` rows, not raw JSON or flattened unlabelled cell concatenation.
6. Chunk description prose semantically with length cap; tables independently by header+row groups; custom fields independently by default, with optional related-field grouping.
7. Every chunk has full `item_uid`, `project_uid`, `revision_uid`, `field_def_uid`, `block_uid`, `chunk_key`; tokens counted using matching model tokenizer where available.
8. Fingerprint = SHA256(exact input bytes + model digest + prompt/prefix + chunker config + table transform version); no re-embed if identical; payload-only changes update filter metadata.
9. Title propagation policy affects how often title changes trigger re-embedding. Compare retrieval quality and cache efficiency before choosing a stable default.

## Example
Raw: `<p style="color:red">The CCU shall handle network failure.</p><table><tr><th>Signal</th><th>Condition</th><th>Action</th></tr><tr><td>IGN</td><td>OFF</td><td>Stop SOME/IP</td></tr></table>`

Text chunk: `Title: Ethernet Communication
Description: The CCU shall handle network failure.`
Table chunk: `Title: Ethernet Communication
Table: Communication Conditions
Signal = IGN; Condition = OFF; Action = Stop SOME/IP.`

Never embed solely the literal HTML tags or JSON serialization unless retrieval evaluation shows it is preferable. Compare variants in M3/M6.

## v0.2 Token Budget 결론
청크 목표값(제안): target 512, maximum 1,024, Description overlap 64, field/title/header/prefix budget 128 tokens. Oversized fields/rows have safe splitting and original source offsets; no Item total length limit. Full source always retained. 모델의 실제 `num_ctx`와 tokenizer/embedding API truncation 동작을 확인한 후 장비 환경 설정. 상세 기준 `CHUNKING_POLICY.md` 참조.
