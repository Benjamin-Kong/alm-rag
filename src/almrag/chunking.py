"""Exact-input bounded chunks with normalized-source provenance."""
import hashlib
import json
import re

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ChunkConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    target_chunk_tokens: int = Field(default=512, gt=0)
    max_chunk_tokens: int = Field(default=1024, gt=0)
    overlap_tokens: int = Field(default=64, ge=0)
    reserved_context_tokens: int = Field(default=128, ge=0)
    min_chunk_tokens: int = Field(default=64, gt=0)
    effective_max_input_tokens: int = Field(default=1024, gt=0)
    safety_margin: int = Field(default=0, ge=0)
    prefix: str = ""

    @model_validator(mode="after")
    def valid_budgets(self):
        if self.target_chunk_tokens > self.max_chunk_tokens:
            raise ValueError("target_chunk_tokens exceeds max_chunk_tokens")
        if self.min_chunk_tokens > self.target_chunk_tokens:
            raise ValueError("min_chunk_tokens exceeds target_chunk_tokens")
        if self.safety_margin >= self.effective_max_input_tokens:
            raise ValueError("safety_margin leaves no input budget")
        if self.overlap_tokens >= min(self.max_chunk_tokens, self.effective_max_input_tokens - self.safety_margin):
            raise ValueError("overlap_tokens must be below the effective input budget")
        return self


class ChunkingError(ValueError):
    def __init__(self, message, code="CHUNKING_FAILED", global_error=False):
        super().__init__(message)
        self.code = code
        self.global_error = global_error



CHUNKER_VERSION = "exact-input-v1"
TABLE_SERIALIZATION_VERSION = "header-value-v1"


def _fail(message, code="INVALID_NORMALIZED_SOURCE"):
    raise ChunkingError(message, code)


def _span(block_id, text, start, end, cell_id=None):
    result = {
        "coordinate_space": "normalized_cell" if cell_id is not None else "normalized_block",
        "block_id": block_id,
        "source_id": cell_id if cell_id is not None else block_id,
        "char_start": start,
        "char_end": end,
        "utf8_byte_start": len(text[:start].encode("utf-8")),
        "utf8_byte_end": len(text[:end].encode("utf-8")),
    }
    if cell_id is not None:
        result["cell_id"] = cell_id
    return result


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def _units(document):
    units = {}
    block_ids = set()
    for block in document["blocks"]:
        block_id = block["block_id"]
        if not isinstance(block_id, str) or not block_id or block_id in block_ids:
            _fail("Missing or duplicate normalized block identity")
        block_ids.add(block_id)
        if block["kind"] == "text":
            units[(block_id, None)] = block["text"]
        elif block["kind"] == "table":
            for cell in block["table"]["cells"]:
                key = (block_id, cell["cell_id"])
                if key in units:
                    _fail("Duplicate table cell identity")
                units[key] = cell["text"]
        else:
            _fail("Unsupported normalized block kind")
    if not all(isinstance(value, str) for value in units.values()):
        _fail("Normalized source text must be Unicode strings")
    inventory = document.get("source_inventory")
    if inventory is not None:
        independently_recorded = {}
        for entry in inventory:
            key = (entry["block_id"], entry.get("cell_id"))
            if key in independently_recorded:
                _fail("Duplicate inventory source unit")
            independently_recorded[key] = entry["text"]
        if independently_recorded != units:
            _fail("Normalized source inventory does not match the source units", "SOURCE_COVERAGE_MISMATCH")
    return units


def _table_structure(table):
    cells = table["cells"]
    by_id = {cell["cell_id"]: cell for cell in cells}
    if len(by_id) != len(cells) or not cells:
        _fail("Empty table or duplicate table cell identities")
    if table.get("source_cell_count", len(cells)) != len(cells):
        _fail("Source cell count does not match table cell inventory", "SOURCE_COVERAGE_MISMATCH")
    grid = table["grid"]
    if not grid or not grid[0] or any(len(row) != len(grid[0]) for row in grid):
        _fail("Table grid must be nonempty and rectangular")
    positions = {cell_id: set() for cell_id in by_id}
    for row_num, row in enumerate(grid):
        for col_num, cell_id in enumerate(row):
            if cell_id not in by_id:
                _fail("Grid references a missing source cell")
            positions[cell_id].add((row_num, col_num))
    for cell in cells:
        for name in ("row", "col", "rowspan", "colspan"):
            value = cell[name]
            if type(value) is not int or value < (1 if name.endswith("span") else 0):
                _fail("Invalid cell coordinates")
        expected = {(row, col)
                    for row in range(cell["row"], cell["row"] + cell["rowspan"])
                    for col in range(cell["col"], cell["col"] + cell["colspan"])}
        if expected != positions[cell["cell_id"]]:
            _fail("Cell span and grid ownership disagree")
    header_rows = table["header_rows"]
    if not any(cell["is_header"] for cell in cells) or any(type(row) is not int or row < 0 or row >= len(grid) for row in header_rows):
        _fail("Headerless or invalid-header table is ambiguous", "AMBIGUOUS_TABLE_HEADERS")
    header_ids = []
    for row in header_rows:
        for cell_id in grid[row]:
            if not by_id[cell_id]["is_header"]:
                _fail("Header row contains a non-header cell", "AMBIGUOUS_TABLE_HEADERS")
            if cell_id not in header_ids:
                header_ids.append(cell_id)
    labels = {}
    for cell in cells:
        if cell["cell_id"] in header_ids:
            continue
        paths = []
        derived_ids = []
        for col in range(cell["col"], cell["col"] + cell["colspan"]):
            path_ids = []
            for row in header_rows:
                candidate = grid[row][col]
                if candidate not in path_ids:
                    path_ids.append(candidate)
                if candidate not in derived_ids:
                    derived_ids.append(candidate)
            if not path_ids and not header_rows:
                continue
            if not path_ids or any(not by_id[id]["text"].strip() for id in path_ids):
                _fail("Table column has no meaningful header", "AMBIGUOUS_TABLE_HEADERS")
            path = " / ".join(by_id[id]["text"] for id in path_ids)
            if path not in paths:
                paths.append(path)
        explicit = cell.get("header_ids", cell.get("headers"))
        if explicit is not None:
            if isinstance(explicit, str):
                explicit = explicit.split()
            if (not explicit and not cell["is_header"]) or any(id not in by_id or not by_id[id]["is_header"] or not by_id[id]["text"].strip() for id in explicit):
                _fail("Cell refers to missing or non-header association", "AMBIGUOUS_TABLE_HEADERS")
            if not set(derived_ids) <= set(explicit):
                _fail("Cell header association loses a column hierarchy", "AMBIGUOUS_TABLE_HEADERS")
            for id in explicit:
                if id not in derived_ids:
                    paths.append(by_id[id]["text"])
        if not paths:
            if cell["is_header"] and cell["text"].strip():
                paths = [cell["text"]]
            else:
                _fail("Cell has no unambiguous header association", "AMBIGUOUS_TABLE_HEADERS")
        labels[cell["cell_id"]] = " | ".join(paths)
    # Repeat every leaf hierarchy so a fragment remains interpretable alone.
    header_paths = []
    for col in range(len(grid[0])) if header_rows else ():
        ids = list(dict.fromkeys(grid[row][col] for row in header_rows))
        path = " / ".join(by_id[id]["text"] for id in ids)
        if not path.strip():
            _fail("Empty table header", "AMBIGUOUS_TABLE_HEADERS")
        if path not in header_paths:
            header_paths.append(path)
    return by_id, header_ids, labels, header_paths


class _Chunker:
    def __init__(self, document, title, field_id, tokenizer, config, model_fingerprint):
        self.document = document
        self.title = title
        self.field_id = field_id
        self.tokenizer = tokenizer
        self.config = config
        self.model_fingerprint = model_fingerprint
        self.limit = min(config.max_chunk_tokens, config.effective_max_input_tokens - config.safety_margin)
        self.results = []
        self.units = _units(document)
        self.tokenizer_id = getattr(tokenizer, "identity", None)
        if not isinstance(self.tokenizer_id, str) or not self.tokenizer_id or not callable(getattr(tokenizer, "count", None)):
            _fail("An explicit exact tokenizer and identity are required", "TOKENIZER_UNAVAILABLE")
        if not isinstance(model_fingerprint, str) or not model_fingerprint:
            _fail("A model fingerprint is required", "MODEL_FINGERPRINT_MISSING")
        self.fingerprint = {
            "config": config.model_dump(), "model": model_fingerprint,
            "tokenizer": self.tokenizer_id, "normalizer_version": document["version"],
            "chunker_version": CHUNKER_VERSION, "table_version": TABLE_SERIALIZATION_VERSION,
        }

    def count(self, text):
        try:
            result = self.tokenizer.count(text)
        except Exception as exc:
            raise ChunkingError("Exact tokenizer failed", "TOKENIZER_FAILED") from exc
        if type(result) is not int or result < 0 or (text and result == 0):
            _fail("Tokenizer returned an invalid exact token count", "TOKENIZER_FAILED")
        return result

    def context(self, block):
        parts = [self.config.prefix] if self.config.prefix else []
        parts.extend((f"Title: {self.title}", f"Field: {self.field_id}"))
        if block.get("heading_path"):
            parts.append("Heading: " + " / ".join(block["heading_path"]))
        return "\n".join(parts) + "\n"

    def target_budget(self, prefix):
        # Reservation controls the soft content target only. The final exact-input
        # limit always counts actual context, even when it exceeds the reservation.
        context_tokens = self.count(prefix)
        payload_target = max(self.config.min_chunk_tokens,
                             self.config.target_chunk_tokens - self.config.reserved_context_tokens)
        return min(self.limit, context_tokens + payload_target)

    def emit(self, block, exact_input, spans, row_ids=(), cell_ids=()):
        count = self.count(exact_input)
        if count > self.limit:
            _fail("Exact embedding input exceeds its token limit", "INPUT_TOO_LARGE")
        content_hash = _digest({**self.fingerprint, "input_text": exact_input})
        self.results.append({
            "chunk_key": _digest({"block_id": block["block_id"], "field_id": self.field_id,
                                  "spans": spans, "content_hash": content_hash}),
            "input_text": exact_input, "input_tokens": count, "content_hash": content_hash,
            "block_id": block["block_id"], "source_span_offsets": spans,
            "row_ids": list(row_ids), "cell_ids": list(cell_ids),
            "tokenizer_id": self.tokenizer_id,
            "effective_max_input_tokens": self.config.effective_max_input_tokens,
        })

    def largest_end(self, source, start, prefix, budget, suffix=""):
        # Search character boundaries, never token-encode/decode roundtrips that can
        # alter Unicode. Every candidate and emitted input uses the injected exact
        # tokenizer. Non-monotonic counters may produce smaller chunks, never an
        # unchecked oversized result.
        if self.count(prefix + suffix) > self.limit:
            _fail("Required context or table header cannot fit", "CONTEXT_TOO_LARGE")
        lo, hi = start, len(source)
        best = start
        while lo <= hi:
            mid = (lo + hi) // 2
            if self.count(prefix + source[start:mid] + suffix) <= budget:
                best, lo = mid, mid + 1
            else:
                hi = mid - 1
        return best

    def text(self, block):
        source = block["text"]
        prefix = self.context(block)
        if self.count(prefix) > self.limit:
            _fail("Required text context cannot fit", "CONTEXT_TOO_LARGE")
        if not source:
            return
        # Boundary offsets include whitespace; there is no strip() on source text.
        boundaries = [m.end() for m in re.finditer(r"\n\s*\n|[.!?。！？](?:\s+|$)", source)]
        start = 0
        while start < len(source):
            hard_end = self.largest_end(source, start, prefix, self.limit)
            if hard_end <= start:
                _fail("One source character cannot fit with its context", "INPUT_TOO_LARGE")
            if hard_end == len(source):
                end = hard_end
            else:
                target = self.target_budget(prefix)
                soft_end = self.largest_end(source, start, prefix, target)
                if soft_end <= start:
                    soft_end = hard_end
                minimum = min(self.config.min_chunk_tokens, self.count(source[start:soft_end]))
                choices = [b for b in boundaries if start < b <= soft_end and self.count(source[start:b]) >= minimum]
                end = max(choices) if choices else soft_end
            self.emit(block, prefix + source[start:end], [_span(block["block_id"], source, start, end)])
            if end == len(source):
                break
            next_start = end
            if self.field_id == "normalized:description" and self.config.overlap_tokens:
                # Bound overlap itself exactly; require progress for very small budgets.
                lo, hi = start + 1, end
                while lo <= hi:
                    mid = (lo + hi) // 2
                    if self.count(source[mid:end]) <= self.config.overlap_tokens:
                        next_start, hi = mid, mid - 1
                    else:
                        lo = mid + 1
                if self.largest_end(source, next_start, prefix, self.limit) <= end:
                    next_start = end
            start = next_start

    def table(self, block):
        table = block["table"]
        by_id, header_ids, labels, header_paths = _table_structure(table)
        prefix = self.context(block)
        if table.get("caption"):
            prefix += "Table: " + table["caption"] + "\n"
        prefix += "Headers: " + "; ".join(header_paths) + "\n"
        header_spans = [_span(block["block_id"], by_id[id]["text"], 0, len(by_id[id]["text"]), id)
                        for id in header_ids]
        if self.count(prefix) > self.limit:
            _fail("Required table headers cannot fit", "CONTEXT_TOO_LARGE")
        pending_text = ""
        pending_spans = []
        pending_rows = []
        pending_cells = []

        def flush():
            nonlocal pending_text, pending_spans, pending_rows, pending_cells
            if pending_cells:
                self.emit(block, prefix + pending_text, header_spans + pending_spans,
                          pending_rows, header_ids + pending_cells)
                pending_text, pending_spans, pending_rows, pending_cells = "", [], [], []

        rows = sorted({cell["row"] for cell in by_id.values() if cell["cell_id"] not in header_ids})
        if not rows:
            self.emit(block, prefix, header_spans, [f"r{row}" for row in table["header_rows"]], header_ids)
        for row in rows:
            row_cells = sorted((cell for cell in by_id.values() if cell["row"] == row and cell["cell_id"] not in header_ids), key=lambda cell: cell["col"])
            row_text = ""
            row_spans = []
            for cell in row_cells:
                row_text += self.cell_prefix(cell, labels[cell["cell_id"]]) + cell["text"] + "\n"
                row_spans.append(_span(block["block_id"], cell["text"], 0, len(cell["text"]), cell["cell_id"]))
            ids = [cell["cell_id"] for cell in row_cells]
            row_ids = list(dict.fromkeys(f"r{r}" for cell in row_cells for r in range(cell["row"], cell["row"] + cell["rowspan"])))
            if self.count(prefix + row_text) <= self.limit:
                if pending_cells and self.count(prefix + pending_text + row_text) > self.target_budget(prefix):
                    flush()
                pending_text += row_text
                pending_spans += row_spans
                pending_rows = list(dict.fromkeys(pending_rows + row_ids))
                pending_cells += ids
                continue
            flush()
            # An oversized row retains each cell's exact header relation and origin
            # identity, splitting only the cell value. A rowspan origin is visited once.
            for cell in row_cells:
                cell_id = cell["cell_id"]
                value = cell["text"]
                cell_prefix = prefix + self.cell_prefix(cell, labels[cell_id])
                source_rows = [f"r{r}" for r in range(cell["row"], cell["row"] + cell["rowspan"])]
                start = 0
                while True:
                    end = self.largest_end(value, start, cell_prefix, self.limit, "\n")
                    if value and end <= start:
                        _fail("Cell association cannot fit a source character", "INPUT_TOO_LARGE")
                    self.emit(block, cell_prefix + value[start:end] + "\n", header_spans + [_span(block["block_id"], value, start, end, cell_id)], source_rows, header_ids + [cell_id])
                    if end == len(value):
                        break
                    start = end
        flush()

    @staticmethod
    def cell_prefix(cell, label):
        rows = ",".join(str(row) for row in range(cell["row"], cell["row"] + cell["rowspan"]))
        cols = ",".join(str(col) for col in range(cell["col"], cell["col"] + cell["colspan"]))
        return f"Row r{cell['row']} [{cell['cell_id']} rows={rows} cols={cols}]: {label}="

    def verify_coverage(self):
        _verify_coverage(self.units, self.results)


def verify_source_coverage(document, chunks):
    """Verify stored source spans against a freshly normalized source inventory."""
    _verify_coverage(_units(document), chunks)


def _verify_coverage(units, chunks):
    spans = {key: [] for key in units}
    for chunk in chunks:
        for span in chunk["source_span_offsets"]:
            key = (span["block_id"], span.get("cell_id"))
            if key not in spans:
                _fail("Chunk refers to a source unit outside the inventory", "SOURCE_COVERAGE_MISMATCH")
            spans[key].append((span["char_start"], span["char_end"]))
    for key, source in units.items():
        end = 0
        for start, stop in sorted(spans[key]):
            if not 0 <= start <= stop <= len(source) or start > end:
                _fail("Chunk spans leave a source gap", "SOURCE_COVERAGE_MISMATCH")
            end = max(end, stop)
        if end != len(source) or (key[1] is not None and not spans[key]):
            _fail("Chunk spans do not cover the complete source", "SOURCE_COVERAGE_MISMATCH")

def make_chunks(document, *, title, field_id, tokenizer, config, model_fingerprint):
    """Return exact-input chunks; all source/schema failures are Item-local.

    Tokenizer injection is a capability contract, not production verification. A
    runtime caller must separately verify its local tokenizer/model pairing.
    No raw HTML is serialized or hashed; its original bytes live in the envelope.
    """
    if not isinstance(config, ChunkConfig):
        config = ChunkConfig.model_validate(config)
    try:
        chunker = _Chunker(document, title, field_id, tokenizer, config, model_fingerprint)
        ordered = sorted(document["blocks"], key=lambda block: block["order"])
        if len({block["order"] for block in ordered}) != len(ordered):
            _fail("Duplicate normalized block order")
        for block in ordered:
            if block["kind"] == "text":
                chunker.text(block)
            else:
                chunker.table(block)
        chunker.verify_coverage()
        return chunker.results
    except ChunkingError:
        raise
    except (KeyError, TypeError, ValueError, IndexError, UnicodeError) as exc:
        raise ChunkingError("Invalid normalized document contract", "INVALID_NORMALIZED_SOURCE") from exc
