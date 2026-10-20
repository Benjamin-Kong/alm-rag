"""SRS-011/016/049/050: loss-aware, inert field normalization."""

from pathlib import Path

import pytest

from almrag.normalization import NormalizationError, normalize_field


FIXTURES = Path(__file__).parent / "fixtures" / "content"


def test_srs011_mixed_dom_order_unicode_and_inert_resources():
    source = ('lead <div>wrapped <p style="color:red">A &amp; 한글 <a href="https://invalid.example">link</a>'
              '<script>secret()</script></p>tail<h2>Section</h2><ul><li>one</li><li>two</li></ul></div> end')
    result = normalize_field(source, "text/html")
    assert [b["text"] for b in result["blocks"]] == [
        "lead", "wrapped", "A & 한글 link", "tail", "Section", "one", "two", "end"]
    assert result["blocks"][5]["heading_path"] == ["Section"]
    assert "style=\"color:red\"" in result["blocks"][2]["raw_html"]
    ref = result["blocks"][2]["source_refs"][0]
    assert ref["char_end"] == len("A & 한글 link")
    assert ref["byte_end"] == len("A & 한글 link".encode())
    assert ref["coordinate_space"] == "normalized_block"
    assert "https://invalid.example" not in result["blocks"][2]["text"]


def test_srs011_multilevel_spans_distinct_cells_and_inventory():
    source = (FIXTURES / "complex_table.html").read_text()
    result = normalize_field(source, "text/html")
    table = next(b["table"] for b in result["blocks"] if b["kind"] == "table")
    assert table["source_cell_count"] == 10
    assert len(table["cells"]) == 10
    assert table["header_rows"] == [0, 1]
    assert table["caption"] == "Signals & actions"
    assert table["grid"][0][0] == table["grid"][1][0]
    assert table["grid"][0][1] == table["grid"][0][2]
    cells = {c["cell_id"]: c for c in table["cells"]}
    last = cells[table["grid"][-1][-1]]
    assert [cells[h]["text"] for h in last["header_ids"]] == ["State", "Action", "B"]
    repeated = [c for c in cells.values() if c["text"] == "OFF"]
    assert len(repeated) == 2 and repeated[0]["cell_id"] != repeated[1]["cell_id"]
    assert '<td data-source="one">OFF</td>' == repeated[0]["raw_html"]
    inventory = [u for u in result["source_inventory"] if u.get("cell_id")]
    assert {u["cell_id"] for u in inventory} == set(cells)
    assert all(c["source_refs"][0]["coordinate_space"] == "normalized_cell" for c in cells.values())


def test_srs011_stable_ids_and_cosmetic_text_invariance():
    first = normalize_field('<p style="color:red">same</p>', "text/html")
    second = normalize_field('<p class="blue">same</p>', "text/html")
    assert first["blocks"][0]["block_id"] == second["blocks"][0]["block_id"]
    assert first["blocks"][0]["text"] == second["blocks"][0]["text"]


@pytest.mark.parametrize(("source", "code"), [
    ('<table><tr><th>A</th><th>B</th></tr><tr><td rowspan="2">x</td><td>y</td></tr></table>', "TABLE_SPAN_OUT_OF_BOUNDS"),
    ('<table><tr><th>A</th><th>B</th><th>C</th></tr><tr><td>x</td><td rowspan="2">y</td><td>z</td></tr><tr><td colspan="2">q</td><td>r</td></tr></table>', "TABLE_OVERLAP"),
    ('<table><tr><td>a</td><td>b</td></tr></table>', "TABLE_HEADERS_AMBIGUOUS"),
    ('<table><tr><th>A</th></tr><tr><td><table><tr><th>X</th></tr></table></td></tr></table>', "TABLE_NESTED_UNSUPPORTED"),
    ('<table><tr><th>A</th></tr><tr><td headers="absent">x</td></tr></table>', "TABLE_HEADERS_INVALID"),
    ('<table><tr><th>A</th></tr><tr><td colspan="0">x</td></tr></table>', "TABLE_SPAN_INVALID"),
    ('<table><tr><th>A</th><th>B</th></tr><tr><td>x</td></tr></table>', "TABLE_GRID_INCOMPLETE"),
])
def test_srs016_invalid_tables_fail_item_locally(source, code):
    with pytest.raises(NormalizationError) as caught:
        normalize_field(source, "text/html")
    assert caught.value.code == code
    assert caught.value.global_error is False


def test_srs016_limited_html_recovery_and_explicit_headers():
    result = normalize_field('<table><tr><th id="h">Name</bogus><tr><td headers="h">Value</table>', "text/html")
    table = result["blocks"][0]["table"]
    assert table["cells"][1]["header_ids"] == [table["cells"][0]["cell_id"]]
    assert table["cells"][1]["text"] == "Value"
    assert any(d["code"] == "HTML_RECOVERED" for d in result["diagnostics"])


def test_srs049_scalar_wiki_and_empty_content_conservative():
    assert normalize_field(42)["blocks"][0]["text"] == "42"
    assert normalize_field(False)["blocks"][0]["text"] == "false"
    assert normalize_field(None)["blocks"] == []
    assert normalize_field('<script>hidden()</script>', "text/html")["blocks"] == []
    result = normalize_field('h1. wiki <b>literal</b>', "text/x-wiki")
    assert result["blocks"][0]["text"] == 'h1. wiki <b>literal</b>'
    assert result["diagnostics"][0]["code"] == "WIKI_UNRENDERED"
    with pytest.raises(NormalizationError, match="FIELD_VALUE_UNSUPPORTED"):
        normalize_field({"type": "TableFieldValue", "rows": [[1, 2]]})


def test_srs049_source_inventory_is_an_independent_snapshot():
    result = normalize_field('<p>Hello</p><table><tr><th>H</th></tr><tr><td>V</td></tr></table>', 'text/html')
    expected = [u["text"] for u in result["source_inventory"]]
    result["blocks"][0]["text"] = "lost"
    result["blocks"][1]["table"]["cells"].clear()
    assert [u["text"] for u in result["source_inventory"]] == expected == ["Hello", "H", "V"]


def test_srs049_table_cell_block_boundaries_preserve_words():
    result = normalize_field('<table><tr><th>H</th></tr><tr><td>Before<p>middle</p>after<br>end</td></tr></table>', 'Html')
    assert result["blocks"][0]["table"]["cells"][1]["text"] == 'Before middle after end'


@pytest.mark.parametrize("source", [
    '<table>lost<tr><th>H</th></tr><tr><td>V</td></tr></table>',
    '<table><tr><th>H</th></tr><tr><td>V</td>lost</tr></table>',
    '<table><tr><th> </th></tr><tr><td>V</td></tr></table>',
])
def test_srs016_table_stray_text_and_empty_headers_fail_closed(source):
    with pytest.raises(NormalizationError) as caught:
        normalize_field(source, 'Html')
    assert caught.value.code in {'TABLE_TEXT_OUTSIDE_CELL', 'TABLE_HEADERS_AMBIGUOUS'}


def test_srs016_header_cycles_fail_locally():
    with pytest.raises(NormalizationError) as caught:
        normalize_field('<table><tr><th id="a" headers="b">A</th><th id="b" headers="a">B</th></tr><tr><td headers="a">x</td><td headers="b">y</td></tr></table>', 'Html')
    assert caught.value.code == 'TABLE_HEADERS_INVALID'


def test_srs049_script_style_comments_and_external_entities_are_inert():
    source = '<!DOCTYPE html [<!ENTITY external SYSTEM "file:///etc/passwd">]><p>Hello<!-- hidden --> world<style>secret</style><script src="https://invalid.example">hidden</script></p>'
    result = normalize_field(source, 'text/html')
    assert result['blocks'][-1]['text'] == 'Hello world'
    assert all('root:' not in b['text'] for b in result['blocks'])


def test_parser_resource_limit_never_accepts_empty_recovered_document():
    """SRS-011/048: parser depth limits must reject, never accept lost text."""
    source='<div>'*300+'DEEP_SENTINEL'+'</div>'*300+'<p>TAIL_SENTINEL</p>'
    with pytest.raises(NormalizationError,match='HTML_PARSE_INCOMPLETE'):
        normalize_field(source,'text/html')
