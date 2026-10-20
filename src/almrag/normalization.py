"""Inert HTML normalization with explicit, loss-aware table ownership.

Raw field bytes belong to the immutable source envelope. ``raw_html`` here is a
DOM fragment (lxml may repair markup), never a claim of byte-identical source.
Offsets describe normalized block/cell text, not raw markup bytes.
"""

from __future__ import annotations

import math
import re
from typing import Any

from lxml import etree, html


VERSION = "dom-table-v1"
_IGNORED = {"script", "style", "template", "noscript"}
_BOUNDARIES = {"p", "div", "li", "ul", "ol", "section", "article", "header", "footer",
               "aside", "blockquote", "pre", "dl", "dt", "dd", "hr", "address", "figure", "figcaption"}
_HEADINGS = {f"h{i}" for i in range(1, 7)}


class NormalizationError(ValueError):
    """A field cannot be normalized without uncertain content loss."""

    global_error = False

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _tag(node: etree._Element) -> str:
    return node.tag.lower() if isinstance(node.tag, str) else ""


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _raw(node: etree._Element) -> str:
    return etree.tostring(node, encoding="unicode", method="html", with_tail=False)


def _inline(node: etree._Element) -> str:
    """Visible text only; resources and script bodies are never evaluated."""
    pieces: list[str] = []

    def visit(element: etree._Element) -> None:
        if _tag(element) in _IGNORED:
            return
        if element.text:
            pieces.append(element.text)
        for child in element:
            if _tag(child) in _BOUNDARIES:
                pieces.append(" ")
            if _tag(child) == "br":
                pieces.append(" ")
            elif isinstance(child.tag, str):
                visit(child)
            if _tag(child) in _BOUNDARIES:
                pieces.append(" ")
            if child.tail:
                pieces.append(child.tail)

    visit(node)
    return _clean("".join(pieces))


def _ref(text: str, dom_path: str, space: str) -> dict:
    return {"coordinate_space": space, "char_start": 0, "char_end": len(text),
            "byte_start": 0, "byte_end": len(text.encode("utf-8")), "dom_path": dom_path}


def _span(cell: etree._Element, name: str) -> int:
    value = cell.get(name, "1")
    if not re.fullmatch(r"[1-9][0-9]*", value):
        raise NormalizationError("TABLE_SPAN_INVALID")
    result = int(value)
    # Prevent hostile spans from allocating an unbounded expanded grid.
    if result > 10000:
        raise NormalizationError("TABLE_SPAN_INVALID")
    return result


def _table(node: etree._Element, block_id: str, inventory: list[dict]) -> dict:
    if node.xpath(".//table"):
        raise NormalizationError("TABLE_NESTED_UNSUPPORTED")
    rows = node.xpath(".//tr")
    original_cells = node.xpath(".//th | .//td")
    if not rows or not original_cells:
        raise NormalizationError("TABLE_EMPTY_OR_UNSTRUCTURED")
    if any(_tag(cell.getparent()) != "tr" for cell in original_cells):
        raise NormalizationError("TABLE_CELL_OUTSIDE_ROW")

    def check_structural_text(element: etree._Element) -> None:
        if _tag(element) in {"th", "td", "caption"} | _IGNORED:
            return
        if element.text and element.text.strip():
            raise NormalizationError("TABLE_TEXT_OUTSIDE_CELL")
        for child in element:
            if isinstance(child.tag, str):
                check_structural_text(child)
            if child.tail and child.tail.strip():
                raise NormalizationError("TABLE_TEXT_OUTSIDE_CELL")

    check_structural_text(node)
    tree = node.getroottree()
    # Capture source ownership before grid/normalization output is constructed.
    source_ids = {cell: f"{block_id}:c{index:06d}" for index, cell in enumerate(original_cells)}
    source_units = [{"unit_id": source_ids[cell], "block_id": block_id,
                     "cell_id": source_ids[cell], "text": _inline(cell),
                     "coordinate_space": "normalized_cell", "dom_path": tree.getpath(cell)}
                    for cell in original_cells]
    occupancy: dict[tuple[int, int], str] = {}
    cells: list[dict] = []
    source_attributes: dict[str, str] = {}
    for row_index, row in enumerate(rows):
        col = 0
        for element in row:
            if _tag(element) not in {"th", "td"}:
                continue
            while (row_index, col) in occupancy:
                col += 1
            rowspan, colspan = _span(element, "rowspan"), _span(element, "colspan")
            if row_index + rowspan > len(rows):
                raise NormalizationError("TABLE_SPAN_OUT_OF_BOUNDS")
            if len(rows) * (col + colspan) > 1_000_000:
                raise NormalizationError("TABLE_GRID_LIMIT")
            cell_id = source_ids[element]
            for r in range(row_index, row_index + rowspan):
                for c in range(col, col + colspan):
                    if (r, c) in occupancy:
                        raise NormalizationError("TABLE_OVERLAP")
                    occupancy[r, c] = cell_id
            text = _inline(element)
            cell = {"cell_id": cell_id, "row": row_index, "col": col,
                    "rowspan": rowspan, "colspan": colspan, "is_header": _tag(element) == "th",
                    "text": text, "raw_html": _raw(element),
                    "source_refs": [_ref(text, tree.getpath(element), "normalized_cell")]}
            if element.get("scope"):
                scope = element.get("scope").lower()
                if scope not in {"row", "col"}:
                    raise NormalizationError("TABLE_SCOPE_UNSUPPORTED")
                if not cell["is_header"]:
                    raise NormalizationError("TABLE_HEADERS_INVALID")
                cell["scope"] = scope
            if element.get("headers") is not None:
                cell["headers"] = element.get("headers").split()
            if element.get("id"):
                identifier = element.get("id")
                if identifier in source_attributes:
                    raise NormalizationError("TABLE_HEADERS_INVALID")
                source_attributes[identifier] = cell_id
            cells.append(cell)
            col += colspan
    if {c["cell_id"] for c in cells} != {u["cell_id"] for u in source_units}:
        raise NormalizationError("TABLE_CELL_COVERAGE")
    width = max(c for _, c in occupancy) + 1
    if len(occupancy) != width * len(rows):
        raise NormalizationError("TABLE_GRID_INCOMPLETE")
    grid = [[occupancy[r, c] for c in range(width)] for r in range(len(rows))]
    by_id = {cell["cell_id"]: cell for cell in cells}
    header_rows = [r for r, row in enumerate(grid) if all(by_id[c]["is_header"] for c in row)]
    for cell in cells:
        if "headers" in cell:
            try:
                headers = [source_attributes[identifier] for identifier in cell["headers"]]
            except KeyError:
                raise NormalizationError("TABLE_HEADERS_INVALID") from None
            if not headers or any(not by_id[h]["is_header"] or h == cell["cell_id"] for h in headers):
                raise NormalizationError("TABLE_HEADERS_INVALID")
        else:
            headers = []
            for header in cells:
                if not header["is_header"] or header is cell:
                    continue
                scope = header.get("scope")
                above = header["row"] + header["rowspan"] <= cell["row"]
                intersects = (header["col"] < cell["col"] + cell["colspan"] and
                              cell["col"] < header["col"] + header["colspan"])
                left = header["col"] + header["colspan"] <= cell["col"]
                same_row = header["row"] <= cell["row"] < header["row"] + header["rowspan"]
                if (scope != "row" and above and intersects and
                    (scope == "col" or header["row"] in header_rows)):
                    headers.append(header["cell_id"])
                elif scope != "col" and left and same_row:
                    headers.append(header["cell_id"])
            # A data cell spanning different leaf column labels cannot preserve
            # a one-to-one association without an explicit headers attribute.
            if not cell["is_header"] and cell["colspan"] > 1:
                col_headers = [by_id[h] for h in headers if by_id[h]["row"] < cell["row"]]
                if any(h["colspan"] < cell["colspan"] for h in col_headers):
                    raise NormalizationError("TABLE_HEADERS_AMBIGUOUS")
        cell["header_ids"] = list(dict.fromkeys(headers))
        if not cell["is_header"] and not cell["header_ids"]:
            raise NormalizationError("TABLE_HEADERS_AMBIGUOUS")
        if not cell["is_header"] and any(not by_id[h]["text"] for h in cell["header_ids"]):
            raise NormalizationError("TABLE_HEADERS_AMBIGUOUS")
    # Explicit references must not introduce cyclic header hierarchies.
    def check_cycle(cell_id: str, path: set[str]) -> None:
        if cell_id in path:
            raise NormalizationError("TABLE_HEADERS_INVALID")
        for header in by_id[cell_id]["header_ids"]:
            check_cycle(header, path | {cell_id})

    for cell in cells:
        check_cycle(cell["cell_id"], set())
    inventory.extend(source_units)
    captions = node.xpath("./caption")
    if len(captions) > 1:
        raise NormalizationError("TABLE_CAPTION_AMBIGUOUS")
    return {"cells": cells, "grid": grid, "header_rows": header_rows,
            "caption": _inline(captions[0]) if captions else None,
            "source_cell_count": len(original_cells)}


def normalize_field(value: Any, source_format: str = "text/plain") -> dict:
    """Normalize one selected field without any I/O or content execution.

    Opaque structured values need an explicit connector contract. They are never
    silently embedded as JSON. Wiki input is retained literally until a verified
    source-side renderer supplies HTML.
    """
    result: dict = {"version": VERSION, "blocks": [], "diagnostics": [], "source_inventory": []}
    if value is None:
        return result
    if isinstance(value, bool):
        value = "true" if value else "false"
    elif isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            raise NormalizationError("FIELD_VALUE_UNSUPPORTED")
        value = str(value)
    elif not isinstance(value, str):
        raise NormalizationError("FIELD_VALUE_UNSUPPORTED")
    if not isinstance(source_format, str):
        raise NormalizationError("FIELD_FORMAT_UNSUPPORTED")
    format_name = source_format.casefold().split(";", 1)[0].strip()
    blocks, inventory = result["blocks"], result["source_inventory"]
    headings: dict[int, str] = {}

    def text_block(text: str, path: str, raw: str | None) -> None:
        text = _clean(text)
        if not text:
            return
        block_id = f"b{len(blocks):06d}"
        unit = {"unit_id": block_id, "block_id": block_id, "text": text,
                "coordinate_space": "normalized_block", "dom_path": path}
        inventory.append(unit)
        blocks.append({"block_id": block_id, "order": len(blocks), "kind": "text", "text": text,
                       "heading_path": list(headings.values()), "raw_html": raw,
                       "source_refs": [_ref(text, path, "normalized_block")]})

    if format_name not in {"text/html", "html", "application/xhtml+xml"}:
        if format_name in {"wiki", "text/x-wiki", "text/wiki", "text/x-polarion-wiki"}:
            result["diagnostics"].append({"code": "WIKI_UNRENDERED", "severity": "warning"})
        elif format_name not in {"text/plain", "plain", "text", "string", "", "json", "source:json"}:
            raise NormalizationError("FIELD_FORMAT_UNSUPPORTED")
        text_block(value, "/field", None)
        return result
    if not value.strip():
        return result
    parser = html.HTMLParser(no_network=True, recover=True)
    try:
        root = html.fragment_fromstring(value, create_parent="div", parser=parser)
    except (etree.ParserError, ValueError, UnicodeError):
        raise NormalizationError("HTML_PARSE_FAILED") from None
    if any(entry.level_name == "FATAL" or entry.type_name in {"ERR_RESOURCE_LIMIT", "ERR_INVALID_CHAR", "ERR_INVALID_ENCODING"} for entry in parser.error_log):
        raise NormalizationError("HTML_PARSE_INCOMPLETE")
    if parser.error_log:
        result["diagnostics"].append({"code": "HTML_RECOVERED", "severity": "warning"})
    tree = root.getroottree()
    pending: list[str] = []
    pending_origin: etree._Element | None = None

    def append(text: str | None, node: etree._Element) -> None:
        nonlocal pending_origin
        if text:
            if pending_origin is None and text.strip():
                pending_origin = node
            pending.append(text)

    def flush() -> None:
        nonlocal pending_origin
        if pending:
            origin = pending_origin if pending_origin is not None else root
            text_block("".join(pending), tree.getpath(origin), _raw(origin))
        pending.clear()
        pending_origin = None

    def walk(node: etree._Element) -> None:
        tag = _tag(node)
        if tag in _IGNORED or not tag:
            return
        if tag == "table":
            flush()
            block_id = f"b{len(blocks):06d}"
            table = _table(node, block_id, inventory)
            blocks.append({"block_id": block_id, "order": len(blocks), "kind": "table", "text": "",
                           "heading_path": list(headings.values()), "raw_html": _raw(node),
                           "source_refs": [{"coordinate_space": "dom", "dom_path": tree.getpath(node)}],
                           "table": table})
            return
        if tag in _HEADINGS:
            flush()
            if node.xpath(".//table"):
                raise NormalizationError("HTML_HEADING_STRUCTURE_UNSUPPORTED")
            level = int(tag[1])
            for previous in list(headings):
                if previous >= level:
                    del headings[previous]
            text = _inline(node)
            if text:
                headings[level] = text
                text_block(text, tree.getpath(node), _raw(node))
            return
        boundary = tag in _BOUNDARIES
        if boundary:
            flush()
        if tag == "br":
            append(" ", node)
        append(node.text, node)
        for child in node:
            walk(child)
            append(child.tail, node)
        if boundary:
            flush()

    walk(root)
    flush()
    return result
