"""SRS-011/012/013/014/048/049: token bounds and complete provenance."""
from copy import deepcopy

import pytest
from pydantic import ValidationError

from almrag.chunking import ChunkConfig, ChunkingError, make_chunks


class FixtureExactTokenizer:
    """Synthetic vocabulary: each Unicode code point is exactly one fixture token."""
    identity = "fixture-codepoint-v1:synthetic-only"

    def count(self, text):
        return len(text)


def document(text):
    return {"version": "normalizer-fixture-v1", "blocks": [{"block_id": "b1", "order": 0,
        "kind": "text", "text": text, "heading_path": ["Section"], "raw_html": text}]}


def table_document(long_value="αβ"):
    cells = [
        {"cell_id": "h1", "row": 0, "col": 0, "rowspan": 1, "colspan": 1, "is_header": True, "text": "Name"},
        {"cell_id": "h2", "row": 0, "col": 1, "rowspan": 1, "colspan": 1, "is_header": True, "text": "Details"},
        {"cell_id": "c1", "row": 1, "col": 0, "rowspan": 2, "colspan": 1, "is_header": False, "text": "same", "header_ids": ["h1"]},
        {"cell_id": "c2", "row": 1, "col": 1, "rowspan": 1, "colspan": 1, "is_header": False, "text": long_value, "header_ids": ["h2"]},
        {"cell_id": "c3", "row": 2, "col": 1, "rowspan": 1, "colspan": 1, "is_header": False, "text": "same", "header_ids": ["h2"]},
    ]
    return {"version": "normalizer-fixture-v1", "blocks": [{"block_id": "t1", "order": 0, "kind": "table", "text": "", "heading_path": [], "table": {"cells": cells, "grid": [["h1", "h2"], ["c1", "c2"], ["c1", "c3"]], "header_rows": [0], "caption": "Example", "source_cell_count": 5}}]}


def chunks(doc, **kwargs):
    return make_chunks(doc, title=kwargs.pop("title", "Title"), field_id=kwargs.pop("field_id", "normalized:description"), tokenizer=kwargs.pop("tokenizer", FixtureExactTokenizer()), config=kwargs.pop("config", ChunkConfig()), model_fingerprint=kwargs.pop("model_fingerprint", "fixture-model-v1"), **kwargs)


def assert_coverage(doc, result):
    for block in doc["blocks"]:
        units = [(None, block["text"])] if block["kind"] == "text" else [(cell["cell_id"], cell["text"]) for cell in block["table"]["cells"]]
        for cell_id, source in units:
            spans = [span for chunk in result for span in chunk["source_span_offsets"] if span["block_id"] == block["block_id"] and span.get("cell_id") == cell_id]
            assert spans, (block["block_id"], cell_id)
            covered = set()
            for span in spans:
                assert span["coordinate_space"] == ("normalized_cell" if cell_id else "normalized_block")
                start, end = span["char_start"], span["char_end"]
                assert span["utf8_byte_start"] == len(source[:start].encode())
                assert span["utf8_byte_end"] == len(source[:end].encode())
                assert source[start:end] in next(chunk["input_text"] for chunk in result if span in chunk["source_span_offsets"])
                covered.update(range(start, end))
            assert covered == set(range(len(source)))


@pytest.mark.parametrize("size", [100, 1024, 8000, 15000])
def test_srs_012_long_sentence_exact_limits_and_full_unicode_coverage(size):
    doc = document("가" * size + " \n\tend")
    result = chunks(doc)
    assert result
    assert all(chunk["input_tokens"] == len(chunk["input_text"]) <= 1024 for chunk in result)
    assert all(chunk["tokenizer_id"] == FixtureExactTokenizer.identity for chunk in result)
    if size >= 1024:
        assert len(result) > 1
    assert_coverage(doc, result)


def test_srs_012_title_field_heading_prefix_and_effective_context_counted():
    config = ChunkConfig(max_chunk_tokens=1024, target_chunk_tokens=512, effective_max_input_tokens=300, safety_margin=25, prefix="instruction")
    result = chunks(document("word " * 1000), title="Long title", config=config)
    assert all(chunk["input_tokens"] <= 275 for chunk in result)
    assert all(all(part in chunk["input_text"] for part in ["instruction", "Long title", "normalized:description", "Section"]) for chunk in result)


def test_srs_012_description_only_overlap_and_custom_field_no_overlap():
    config = ChunkConfig(target_chunk_tokens=200, max_chunk_tokens=250, min_chunk_tokens=16, reserved_context_tokens=30, overlap_tokens=20)
    doc = document("abcdefghij " * 200)
    description = chunks(doc, config=config)
    custom = chunks(doc, config=config, field_id="source:description")
    def intervals(result):
        return [(c["source_span_offsets"][0]["char_start"], c["source_span_offsets"][0]["char_end"]) for c in result]
    assert any(left[1] > right[0] for left, right in zip(intervals(description), intervals(description)[1:]))
    assert all(left[1] == right[0] for left, right in zip(intervals(custom), intervals(custom)[1:]))
    assert_coverage(doc, description)
    assert_coverage(doc, custom)


def test_srs_013_table_long_cell_repeated_headers_ids_and_utf8_spans():
    doc = table_document("표 " * 7500)
    result = chunks(doc)
    assert len(result) > 15
    assert all(chunk["input_tokens"] <= 1024 for chunk in result)
    assert all("Name" in chunk["input_text"] and "Details" in chunk["input_text"] and chunk["row_ids"] for chunk in result)
    assert any("c1" in chunk["input_text"] and "rows=1,2" in chunk["input_text"] for chunk in result)
    assert_coverage(doc, result)
    c1_spans = [span for c in result for span in c["source_span_offsets"] if span.get("cell_id") == "c1"]
    assert len(c1_spans) == 1


def test_srs_013_multirow_header_hierarchy_repeated_and_duplicate_values_distinct():
    doc = table_document()
    table = doc["blocks"][0]["table"]
    for cell in table["cells"]:
        cell["row"] += 1
    table["cells"].insert(0, {"cell_id": "top", "row": 0, "col": 0, "rowspan": 1, "colspan": 2, "is_header": True, "text": "Group"})
    table["grid"].insert(0, ["top", "top"])
    table["header_rows"] = [0, 1]
    table["source_cell_count"] += 1
    for cell in table["cells"]:
        if not cell["is_header"]:
            cell["header_ids"].insert(0, "top")
    result = chunks(doc)
    assert all("Group / Name" in c["input_text"] and "Group / Details" in c["input_text"] for c in result)
    assert {"c1", "c3"} <= {id for c in result for id in c["cell_ids"]}
    assert_coverage(doc, result)


@pytest.mark.parametrize("mutation", ["headerless", "missing_cell", "missing_header", "conflicting_grid", "wrong_count"])
def test_srs_013_ambiguous_or_incomplete_table_fails_item_locally(mutation):
    doc = table_document()
    table = doc["blocks"][0]["table"]
    if mutation == "headerless":
        table["header_rows"] = []
        for cell in table["cells"]:
            cell["is_header"] = False
    elif mutation == "missing_cell":
        table["cells"].pop()
    elif mutation == "missing_header":
        table["cells"][2]["header_ids"] = ["unknown"]
    elif mutation == "conflicting_grid":
        table["grid"][2][0] = "c2"
    else:
        table["source_cell_count"] += 1
    with pytest.raises(ChunkingError) as exc:
        chunks(doc)
    assert not exc.value.global_error
    assert exc.value.code


def test_srs_012_unfittable_context_or_table_header_never_truncated():
    with pytest.raises(ChunkingError):
        chunks(document("x"), title="t" * 2000)
    doc = table_document()
    doc["blocks"][0]["table"]["cells"][0]["text"] = "h" * 2000
    with pytest.raises(ChunkingError):
        chunks(doc)


def test_srs_014_hash_stability_and_invalidation_cosmetic_raw_html_ignored():
    doc = document("Some content.")
    original = chunks(doc)
    changed = deepcopy(doc)
    changed["revision_uid"] = "different-revision"
    changed["blocks"][0]["raw_html"] = '<p style="color:red">Some content.</p>'
    assert chunks(changed) == original
    for result in [chunks(doc, model_fingerprint="model-v2"), chunks(doc, config=ChunkConfig(reserved_context_tokens=129)), chunks(doc, title="New title")]:
        assert result[0]["content_hash"] != original[0]["content_hash"]
    tokenizer = FixtureExactTokenizer()
    tokenizer.identity = "fixture-v2"
    assert chunks(doc, tokenizer=tokenizer)[0]["content_hash"] != original[0]["content_hash"]


def test_srs_049_inventory_cannot_omit_or_modify_source_units():
    doc = document("preserved")
    doc["source_inventory"] = [{"unit_id": "b1", "block_id": "b1", "text": "different", "coordinate_space": "normalized_unicode"}]
    with pytest.raises(ChunkingError):
        chunks(doc)
    doc["source_inventory"][0]["text"] = "preserved"
    assert_coverage(doc, chunks(doc))
    doc["source_inventory"].append({"unit_id": "missing", "block_id": "missing", "text": "lost", "coordinate_space": "normalized_unicode"})
    with pytest.raises(ChunkingError):
        chunks(doc)


def test_srs_012_semantic_breaks_and_block_order_retained():
    doc = document("First paragraph.\n\nSecond paragraph!\n")
    doc["blocks"].append({"block_id": "b2", "order": 1, "kind": "text", "text": "End", "heading_path": []})
    result = chunks(doc)
    assert [c["block_id"] for c in result] == ["b1", "b2"]
    assert_coverage(doc, result)


@pytest.mark.parametrize("kwargs", [{"max_chunk_tokens": 0}, {"overlap_tokens": -1}, {"safety_margin": 1024}, {"target_chunk_tokens": 2000}, {"overlap_tokens": 1024}])
def test_srs_012_invalid_configuration_rejected(kwargs):
    with pytest.raises(ValidationError):
        ChunkConfig(**kwargs)


def test_srs_012_unverified_or_invalid_counter_rejected():
    class BadCounter:
        identity = "invalid"
        def count(self, text):
            return -1
    with pytest.raises(ChunkingError):
        chunks(document("text"), tokenizer=BadCounter())


def test_srs_012_exact_counter_not_character_estimate_and_whitespace_coverage():
    class FixtureUtf8Tokenizer:
        identity = "fixture-each-utf8-byte-is-token:synthetic-only"
        def count(self, text):
            return len(text.encode("utf-8"))
    doc = document("\n가😀\t " * 2000)
    result = chunks(doc, tokenizer=FixtureUtf8Tokenizer())
    assert all(c["input_tokens"] == len(c["input_text"].encode()) <= 1024 for c in result)
    assert_coverage(doc, result)


def test_srs_049_table_inventory_missing_cell_and_text_mismatch_rejected():
    doc = table_document()
    doc["source_inventory"] = [{"unit_id": c["cell_id"], "block_id": "t1", "cell_id": c["cell_id"], "text": c["text"], "coordinate_space": "normalized_unicode"} for c in doc["blocks"][0]["table"]["cells"]]
    assert_coverage(doc, chunks(doc))
    doc["source_inventory"].pop()
    with pytest.raises(ChunkingError, match="inventory"):
        chunks(doc)


def test_srs_013_empty_cell_preserves_identity_and_metadata():
    doc = table_document("")
    result = chunks(doc)
    assert "c2" in {id for c in result for id in c["cell_ids"]}
    assert_coverage(doc, result)


def test_srs_012_duplicate_block_ids_fail_instead_of_overwriting_source():
    doc = document("one")
    doc["blocks"].append({**doc["blocks"][0], "order": 1, "text": "two"})
    with pytest.raises(ChunkingError):
        chunks(doc)


def test_srs_012_reserved_context_is_a_soft_payload_budget():
    doc = document("x" * 3000)
    common = {"target_chunk_tokens": 400, "max_chunk_tokens": 600, "overlap_tokens": 0}
    low_reserve = chunks(doc, config=ChunkConfig(**common, reserved_context_tokens=100))
    high_reserve = chunks(doc, config=ChunkConfig(**common, reserved_context_tokens=200))
    assert high_reserve[0]["source_span_offsets"][0]["char_end"] < low_reserve[0]["source_span_offsets"][0]["char_end"]
    assert_coverage(doc, low_reserve)
    assert_coverage(doc, high_reserve)


def test_srs_013_explicit_row_headers_need_no_invented_column_names():
    doc = {"version": "fixture-v1", "blocks": [{"block_id": "rowtable", "order": 0, "kind": "table", "text": "", "heading_path": [], "table": {
        "cells": [{"cell_id": "rh", "row": 0, "col": 0, "rowspan": 1, "colspan": 1, "is_header": True, "scope": "row", "text": "Status", "header_ids": []},
                  {"cell_id": "value", "row": 0, "col": 1, "rowspan": 1, "colspan": 1, "is_header": False, "text": "Value " * 1000, "header_ids": ["rh"]}],
        "grid": [["rh", "value"]], "header_rows": [], "source_cell_count": 2}}]}
    result = chunks(doc)
    assert all("Status" in c["input_text"] for c in result)
    assert all("Column1" not in c["input_text"] for c in result)
    assert_coverage(doc, result)
