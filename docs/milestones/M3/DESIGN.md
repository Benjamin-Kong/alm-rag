# M3 processing contracts and boundaries

## Normalization

normalize_field(value,source_format='text/plain')->dict {version,blocks,diagnostics}. A block is {block_id,order,kind:'text'|'table',text,heading_path,raw_html,table?}. Use lxml HTML parsing of supplied strings only; no URL/file resolution, scripts/external resources or source-side rendering. Raw source remains in immutable M2 envelope, cosmetic normalization affects only derived content. Preserve ordered paragraphs/lists/headings/tables. Wiki without verified HTML must use an explicit conservative fallback/diagnostic or fail rather than pretend it is rendered HTML.

Table schema: {cells:[{cell_id,row,col,rowspan,colspan,is_header,text,raw_html,scope?,headers?}],grid:[[cell_id]],header_rows:[row indexes],caption}. Cell identities and expanded grid preserve original cell ownership, spans and header hierarchy. Invalid overlap/ambiguous header associations or unsupported nested structure fails Item-locally. Limited fallback must preserve and validate all text/cell associations, otherwise no derived run is accepted. Never silently flatten/lossily recover a table.

Offsets distinguish normalized Unicode character/UTF8 byte coordinates and DOM/cell provenance from original raw HTML bytes. Chunks reference exact block/cell text spans and coverage validation compares against independent normalized source units/cells. Original field bytes remain recoverable from the envelope. Do not mislabel normalized spans as raw HTML offsets.

## Token-bound chunks

make_chunks(document,*,title,field_id,tokenizer,config,model_fingerprint)->list[dict]. Inject tokenizer.count(exact_input)->int with explicit identity. ChunkConfig follows512 target/1024 max/64 Description-only overlap/128 reserved context proposals; the entire input includes title/field/heading/prefix/table headers. Effective bound is min(config max,verified model effective context-safety margin). No Item length limit, no silent truncation. Split text at semantic boundaries then safe subspans as necessary; custom fields separate; tables independently serialize Header=Value with repeated hierarchy/row IDs and bounded cell fragments if a row is oversized. If prefix/header/atomic association cannot fit, fail rather than drop it. Verify span/cell union completeness and exact token count for every chunk.

Output chunk metadata includes stable chunk_key, exact input_text/input_tokens/content_hash, block_id, source_span_offsets with explicit coordinate space, row_ids/cell IDs and tokenizer_id/effective_max_input_tokens. Content hash is independent of revision UID but includes exact input bytes/model digest/tokenizer artifact/processing config/normalizer/chunker/table versions. Persistence adds project/item/revision/field ownership. Never share a mutable chunk row across revisions.

## Runtime and selective embedding

Runtime profile pins model name/digest, tokenizer identity+artifact checksum, context, safety margin, vector dimension, prefix/config and verification evidence. Model/tokenizer drift fails closed. Production local tokenizer loads only an explicitly supplied local artifact; no automatic model/tokenizer download. A conservative character counter is allowed only in named synthetic fixtures, never as verified production evidence.

Ollama /api/embed requests use truncate:false and bounded authenticated TLS/no-redirect/no-proxy HTTP. Check finite vector/dimension/count and per-input prompt_eval_count against the matched tokenizer; reject unexpected truncation/token mismatch. Keep cache project-scoped and keyed by complete input/config/model fingerprint. Unchanged chunks reuse validated vectors with zero embed calls. Runtime unverified/model mismatch is global BLOCKED; individual parse/table/input failures are Item-local. No Qdrant/index/active pointer changes.

Additive processing-run/config/snapshot/membership/vector-cache tables avoid collisions with v1 content_blocks/chunks when the same revision is reprocessed under a new configuration. Run namespaces belong in persisted block/chunk identities; cache identity stays revision-independent. Commit an Item's derived artifacts atomically with current job fencing token. Partial Item output is not marked ready, active content remains unchanged. PROCESS and EMBED are independent; full SYNC/INDEX remain unavailable until M4. Pin source revision and effective typed field policy in each job snapshot.

Typed field references distinguish normalized:title/description from source:{original_id}; scope policies inherit instance defaults then project overrides then Tracker/Type overrides. Never infer selected source fields from display labels or alias strings. Complete unselected fields remain raw/filterable. No M5 wizard dependency.

## Evidence and unresolved runtime limits

Official sources read2026-10-20: [Ollama embed API](https://docs.ollama.com/api/embed), [model catalog](https://ollama.com/library/embeddinggemma-2), [lxml HTML parser](https://lxml.de/lxmlhtml.html), [tokenizers API](https://huggingface.co/docs/tokenizers/api/tokenizer). Ollama catalog metadata and prose context values conflict; neither establishes deployed effective limits. No real runtime/tokenizer or model weights are currently installed. Record actual hardware/runtime calibration as NOT VERIFIED until executed; mock evidence never changes that status.
