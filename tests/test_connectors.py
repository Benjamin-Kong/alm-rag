"""Synthetic source contract tests: SRS-001/003..008/010/022/045..047/049/058.

No fixtures contain production data and no test creates a network client.
"""
from copy import deepcopy
import json
from pathlib import Path

import httpx
import pytest

from almrag.connectors import CodebeamerConnector, ConnectorError, PolarionConnector


class FakeClient:
    base_url = "https://alm.example.invalid"

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get_json(self, path, params=None):
        self.calls.append(("GET", path, params))
        result = self.routes[path]
        if callable(result):
            result = result(params or {})
        if isinstance(result, Exception):
            raise result
        return deepcopy(result)

    def request(self, method, path, params=None, json=None, max_bytes=None):
        self.calls.append((method, path, {"json": json, "max_bytes": max_bytes}))
        return httpx.Response(200, content=self.routes[(method, path)], request=httpx.Request(method, self.base_url + path))


def cb_item_client(**changes):
    item = {"id": 100, "name": "한글 ☃", "tracker": {"id": 31}, "version": 4,
            "modifiedAt": "2026-10-20T00:00:00Z", "descriptionFormat": "Html",
            "description": "<table><tr><td>큰 표 ☃</td></tr></table>" * 2000,
            "futureStandard": {"unrecognized": [1, False, "값"]},
            "customFields": [{"fieldId": 900, "name": "Custom table", "type": "TableFieldValue",
                              "values": [[{"fieldId": 901, "value": "nested"}]]}]}
    item.update(changes)
    return FakeClient({"/v3/items/100": item,
        "/v3/items/100/relations": {"outgoingAssociations": [{"type": "depends",
            "id": 99, "itemRevision": {"id": 101, "version": 3}}]},
        "/v3/items/100/attachments": {"page": 1, "pageSize": 1, "total": 1,
            "attachments": [{"id": 7, "name": "../../sample.txt"}]},
        ("GET", "/v3/attachments/7/content"): b"attachment\x00data",
        ("POST", "/v3/projects/1/wiki2html"): "<p>서버 HTML</p>".encode()})


def polarion_client(**changes):
    attrs = {"id": "REQ-1", "type": "requirement", "title": "한국어",
             "description": {"type": "text/html", "value": "<table><tr><td>보존</td></tr></table>" * 2000},
             "updated": "2026-10-20T00:00:00Z", "futureCustom": [False, {"표": "☃"}]}
    attrs.update(changes)
    return FakeClient({"/projects/p/workitems/REQ-1": {"data": {"type": "workitems", "id": "p/REQ-1",
        "attributes": attrs, "links": {"self": "https://alm.example.invalid/projects/p/workitems/REQ-1"}}},
        "/projects/p/workitems/REQ-1/linkedworkitems": {"data": [{"id": "p/REQ-1/parent/other/REQ-2",
            "attributes": {"role": "parent"}, "relationships": {"workItem": {"data": {"id": "other/REQ-2"}}}}]},
        "/projects/p/workitems/REQ-1/backlinkedworkitems": {"data": []},
        "/projects/p/workitems/REQ-1/attachments": {"data": [{"id": "p/REQ-1/file.txt",
            "attributes": {"fileName": "file.txt"}}]},
        ("GET", "/projects/p/workitems/REQ-1/attachments/file.txt/content"): b"\xffbinary"})


@pytest.mark.parametrize("cls,path,key", [(CodebeamerConnector, "/v3/projects", "projects"),
                                          (PolarionConnector, "/projects", "data")])
def test_srs_001_045_three_projects_and_probe(cls, path, key):
    def page(params):
        number = params.get("page", params.get("page[number]", 1))
        if cls is CodebeamerConnector:
            return {"page": number, "pageSize": 2, "total": 3,
                    key: [{"id": i, "name": f"Synthetic {i}"} for i in ([1, 2] if number == 1 else [3])]}
        return {key: [{"id": str(i), "attributes": {"name": f"Synthetic {i}"}} for i in ([1, 2] if number == 1 else [3])],
                "links": {"next": "/projects?page[number]=2" if number == 1 else None}}
    client = FakeClient({path: page})
    connector = cls(client)
    assert [p["id"] for p in connector.list_projects()] == ["1", "2", "3"]
    assert connector.probe()["read_only"] is True


def test_srs_003_046_codebeamer_tracker_instance_ids():
    c = CodebeamerConnector(FakeClient({"/v3/projects/1/trackers": [
        {"id": 31, "name": "Requirements", "type": {"id": 1, "name": "Requirement"}},
        {"id": 32, "name": "Requirements", "type": {"id": 1}}],
        "/v3/trackers/31/fields": [{"id": 900, "name": "Custom"}]}))
    assert [s["id"] for s in c.list_scopes("1")] == ["31", "32"]
    assert all(s["kind"] == "TRACKER" for s in c.list_scopes("1"))
    assert c.list_fields("1", ["31"])[0]["id"] == "900"
    with pytest.raises(ConnectorError):
        c.list_fields("1", ["1"])


def test_srs_003_046_polarion_type_enumeration_and_fields():
    c = PolarionConnector(FakeClient({"/projects/p/enumerations/~/workitem-type/~": {
        "data": {"attributes": {"options": [{"id": "requirement", "name": "Requirements"}, {"id": "bug", "name": "Bug"}]}}},
        "/projects/p/actions/getFieldsMetadata": {"data": {"attributes": {
            "title": {"label": "Title", "type": {"kind": "string"}},
            "custom": {"label": "커스텀", "type": {"kind": "structure"}}}}}}))
    assert c.list_scopes("p")[0] == {"id": "requirement", "name": "Requirements", "kind": "WORK_ITEM_TYPE"}
    assert {f["id"] for f in c.list_fields("p", ["requirement"])} == {"title", "custom"}
    with pytest.raises(ConnectorError):
        c.list_fields("p", ["31"])


def test_srs_004_006_010_022_049_cb_full_item():
    client = cb_item_client()
    item = CodebeamerConnector(client).get_item("1", "100")
    assert item["revision"] == "4" and item["scope_id"] == "31"
    assert item["description"]["raw"] == client.routes["/v3/items/100"]["description"]
    assert item["description"]["html"] == item["description"]["raw"]
    assert item["raw"]["futureStandard"]["unrecognized"] == [1, False, "값"]
    assert any(f["source_field_id"] == "900" and f["raw_value"][0][0]["value"] == "nested" for f in item["fields"])
    assert any(f["source_field_id"] == "futureStandard" for f in item["fields"])
    assert item["relations"] == [{"type": "depends", "target_id": "101"}]
    assert item["deleted"] is False
    assert not any(call[0] != "GET" for call in client.calls)


@pytest.mark.parametrize("verified", [False, True])
def test_srs_010_wiki_renderer_explicit_verification(verified):
    client = cb_item_client(descriptionFormat="Wiki", description="!! 위키")
    item = CodebeamerConnector(client, renderer_verified=verified).get_item("1", "100")
    assert item["description"]["raw"] == "!! 위키"
    posts = [call for call in client.calls if call[0] == "POST"]
    if verified:
        assert item["description"]["html"] == "<p>서버 HTML</p>"
        assert posts[0][2]["json"] == {"contextId": 100, "contextVersion": 4,
            "markup": "!! 위키", "renderingContextType": "TRACKER_ITEM"}
    else:
        assert not posts and "html" not in item["description"]
        assert "WIKI_RENDERER_UNVERIFIED" in item["diagnostics"]


def test_srs_004_006_010_022_049_polarion_full_item_no_invented_revision():
    client = polarion_client()
    item = PolarionConnector(client).get_item("p", "REQ-1")
    assert item["revision"] is None and item["scope_id"] == "requirement"
    assert len(item["description"]["raw"]) > 50000
    assert item["raw"]["data"]["attributes"]["futureCustom"] == [False, {"표": "☃"}]
    assert item["relations"] == [{"type": "parent", "target_id": "other/REQ-2"}]
    assert any(f["source_field_id"] == "futureCustom" for f in item["fields"])
    assert item["deleted"] is False


@pytest.mark.parametrize("factory,cls,project,itemid", [(cb_item_client, CodebeamerConnector, "1", "100"),
    (polarion_client, PolarionConnector, "p", "REQ-1")])
def test_srs_005_053_attachment_uses_injected_bounded_transport(factory, cls, project, itemid):
    client = factory()
    connector = cls(client)
    attachment = connector.get_item(project, itemid)["attachments"][0]
    assert connector.download_attachment(project, itemid, attachment)
    assert client.calls[-1][0] == "GET"
    assert 0 < client.calls[-1][2]["max_bytes"] <= 100 * 1024 * 1024


@pytest.mark.parametrize("cls,path,payload", [
    (CodebeamerConnector, "/v3/projects", {"page": 1, "total": 3, "pageSize": 2, "projects": [{"id": 1}, {"id": 2}]}),
    (PolarionConnector, "/projects", {"data": [{"id": "p"}], "links": {"next": "/projects?page[number]=1"}})])
def test_srs_007_repeated_page_fails_globally(cls, path, payload):
    with pytest.raises(ConnectorError) as error:
        cls(FakeClient({path: payload})).list_projects()
    assert error.value.global_error and error.value.code.startswith("PAGINATION")


def test_srs_007_partial_page_is_not_silent_success():
    c = CodebeamerConnector(FakeClient({"/v3/projects": {"page": 1, "total": 3, "pageSize": 2, "projects": []}}))
    with pytest.raises(ConnectorError) as error:
        c.list_projects()
    assert error.value.global_error


@pytest.mark.parametrize("bad", ["../secret", "x/y", "x?token=secret", "x%2fy", ""])
def test_srs_001_path_segments_reject_unsafe_ids(bad):
    with pytest.raises(ConnectorError):
        CodebeamerConnector(FakeClient({})).list_scopes(bad)


def test_srs_007_codebeamer_refs_are_latest_and_selected():
    c = CodebeamerConnector(FakeClient({"/v3/projects/1/trackers": [{"id": 31}],
        "/v3/trackers/31/items": {"page": 1, "total": 2, "pageSize": 2,
            "itemRefs": [{"id": 100, "version": 4}, {"id": 101}]}}))
    refs = list(c.iter_refs("1", ["31"]))
    assert refs[0]["id"] == "100" and refs[0]["scope_id"] == "31"
    assert refs[0]["revision"] == "4"


def test_srs_007_polarion_refs_request_all_fields_and_filter_types():
    client = FakeClient({"/projects/p/enumerations/~/workitem-type/~": {"data": {"attributes": {"options": [{"id": "requirement"}, {"id": "bug"}]}}},
        "/projects/p/workitems": {"data": [{"id": "p/REQ-1", "attributes": {"type": "requirement"}},
                                           {"id": "p/BUG-1", "attributes": {"type": "bug"}}]}})
    refs = list(PolarionConnector(client).iter_refs("p", ["requirement"]))
    assert [r["id"] for r in refs] == ["REQ-1"]
    assert client.calls[-1][2]["fields[workitems]"] == "@all"


def test_srs_001_045_errors_are_sanitized():
    response = httpx.Response(403, request=httpx.Request("GET", "https://secret:password@host/?token=private"))
    failure = httpx.HTTPStatusError("private raw response", request=response.request, response=response)
    with pytest.raises(ConnectorError) as error:
        CodebeamerConnector(FakeClient({"/v3/projects": failure})).list_projects()
    assert error.value.code == "HTTP_403" and not error.value.global_error
    assert "private" not in str(error.value) and "password" not in str(error.value)


def test_srs_005_codebeamer_official_attachment_content_route():
    client = cb_item_client()
    client.routes[("GET", "/v3/attachments/7/content")] = b"official-route"
    connector = CodebeamerConnector(client)
    attachment = connector.get_item("1", "100")["attachments"][0]
    assert attachment["path"] == "/v3/attachments/7/content"
    assert connector.download_attachment("1", "100", attachment) == b"official-route"


def test_srs_006_polarion_resource_revision_preserved():
    client = polarion_client()
    client.routes["/projects/p/workitems/REQ-1"]["data"]["revision"] = "2500"
    assert PolarionConnector(client).get_item("p", "REQ-1")["revision"] == "2500"


@pytest.mark.parametrize("cls,path,payload", [
    (CodebeamerConnector, "/v3/projects", {"projects": [{"id": 1}, {"id": 1}], "total": 2}),
    (PolarionConnector, "/projects", {"data": [{"id": "p"}, {"id": "p"}]})])
def test_srs_007_duplicate_catalog_ids_fail(cls, path, payload):
    with pytest.raises(ConnectorError) as error:
        cls(FakeClient({path: payload})).list_projects()
    assert error.value.global_error


def test_srs_007_polarion_global_page_limit(monkeypatch):
    import almrag.connectors as connectors
    monkeypatch.setattr(connectors, "MAX_PAGES", 2)
    def page(params):
        page = params["page[number]"]
        return {"data": [{"id": str(page)}], "links": {"next": f"/projects?page[number]={page + 1}"}}
    with pytest.raises(ConnectorError, match="PAGINATION_LIMIT"):
        PolarionConnector(FakeClient({"/projects": page})).list_projects()


def test_srs_005_forged_attachment_path_is_never_requested():
    client = cb_item_client()
    with pytest.raises(ConnectorError, match="INVALID_ATTACHMENT_PATH"):
        CodebeamerConnector(client).download_attachment("1", "100", {"id": "7", "path": "https://attacker.invalid/data"})
    assert client.calls == []


def test_srs_008_not_found_never_becomes_deleted():
    response = httpx.Response(404, request=httpx.Request("GET", "https://alm.example.invalid/v3/items/100"))
    failure = httpx.HTTPStatusError("not found", request=response.request, response=response)
    with pytest.raises(ConnectorError) as error:
        CodebeamerConnector(FakeClient({"/v3/items/100": failure})).get_item("1", "100")
    assert error.value.code == "HTTP_404" and not error.value.global_error


MATRIX = json.loads((Path(__file__).parent / "fixtures/alm/project_matrix.json").read_text())


@pytest.mark.parametrize("row", MATRIX["codebeamer"])
def test_srs_001_003_004_005_three_codebeamer_projects(row):
    project, scope, itemid = row["project_id"], row["scope_id"], row["item_id"]
    template = cb_item_client()
    routes = {}
    for key, value in template.routes.items():
        key = tuple(part.replace("/100", "/" + itemid) for part in key) if isinstance(key, tuple) else key.replace("/100", "/" + itemid)
        routes[key] = value
    raw = routes[f"/v3/items/{itemid}"]
    raw["id"], raw["tracker"] = int(itemid), {"id": int(scope)}
    routes[f"/v3/projects/{project}/trackers"] = [{"id": int(scope), "name": "Synthetic requirements"}]
    routes[f"/v3/trackers/{scope}/items"] = {"itemRefs": [{"id": int(itemid), "version": 4}], "total": 1}
    routes[f"/v3/trackers/{scope}/fields"] = [{"id": 900, "name": "Custom table"}]
    c = CodebeamerConnector(FakeClient(routes))
    assert c.list_scopes(project)[0]["id"] == scope
    assert c.list_fields(project, [scope])[0]["id"] == "900"
    assert list(c.iter_refs(project, [scope]))[0]["id"] == itemid
    item = c.get_item(project, itemid)
    assert item["project_id"] == project and item["scope_id"] == scope
    assert c.download_attachment(project, itemid, item["attachments"][0]) == b"attachment\x00data"


@pytest.mark.parametrize("row", MATRIX["polarion"])
def test_srs_001_003_004_005_three_polarion_projects(row):
    project, scope, itemid = row["project_id"], row["scope_id"], row["item_id"]
    template = polarion_client()
    def rename(key):
        return key.replace("/projects/p/", "/projects/" + project + "/").replace("/REQ-1", "/" + itemid)
    routes = {(tuple(rename(part) for part in key) if isinstance(key, tuple) else rename(key)): value
              for key, value in template.routes.items()}
    resource = routes[f"/projects/{project}/workitems/{itemid}"]["data"]
    resource["id"] = project + "/" + itemid
    resource["attributes"]["id"], resource["attributes"]["type"] = itemid, scope
    routes[f"/projects/{project}/workitems/{itemid}/attachments"]["data"][0]["id"] = f"{project}/{itemid}/file.txt"
    routes[f"/projects/{project}/enumerations/~/workitem-type/~"] = {"data": {"attributes": {"options": [{"id": scope}]}}}
    routes[f"/projects/{project}/actions/getFieldsMetadata"] = {"data": {"attributes": {"futureCustom": {"label": "Custom"}}}}
    routes[f"/projects/{project}/workitems"] = {"data": [resource]}
    c = PolarionConnector(FakeClient(routes))
    assert c.list_scopes(project)[0]["id"] == scope
    assert c.list_fields(project, [scope])[0]["id"] == "futureCustom"
    assert list(c.iter_refs(project, [scope]))[0]["id"] == itemid
    item = c.get_item(project, itemid)
    assert item["project_id"] == project and item["scope_id"] == scope
    assert c.download_attachment(project, itemid, item["attachments"][0]) == b"\xffbinary"


@pytest.mark.parametrize("code,global_error,stop_state,retryable,status", [
    ("SERVER_PAUSED", True, "PAUSED", True, 429),
    ("UNAUTHORIZED", True, "BLOCKED", False, 401),
    ("FORBIDDEN", False, "BLOCKED", False, 403),
    ("CIRCUIT_OPEN", True, "PAUSED", True, None),
])
def test_srs_054_shared_transport_error_metadata_survives_valueerror(code, global_error, stop_state, retryable, status):
    # Main AlmError is a ValueError. Its sanitized control metadata must take
    # precedence over generic source JSON/shape error handling.
    class SharedError(ValueError):
        pass
    failure = SharedError("must not serialize upstream body")
    failure.code, failure.global_error = code, global_error
    failure.stop_state, failure.retryable, failure.status = stop_state, retryable, status
    client = FakeClient({"/v3/projects": failure})
    with pytest.raises(ConnectorError) as caught:
        CodebeamerConnector(client).list_projects()
    result = caught.value
    assert (result.code, result.global_error, result.stop_state, result.retryable, result.status) == (
        code, global_error, stop_state, retryable, status)
    assert "upstream body" not in str(result)


def test_srs_055_lease_lost_propagates_through_connector():
    from almrag.queue import LeaseLost
    failure = LeaseLost("lease revoked")
    with pytest.raises(LeaseLost) as caught:
        CodebeamerConnector(FakeClient({"/v3/projects": failure})).list_projects()
    assert caught.value is failure


@pytest.mark.parametrize("cls", [CodebeamerConnector, PolarionConnector])
def test_srs_004_normalized_fields_are_explicit_and_not_source_catalog_ids(cls):
    assert cls(FakeClient({})).normalized_fields == ("title", "description")


def test_catalog_listing_is_requested_once_for_many_trackers():
    client = FakeClient({"/v3/projects": [{"id": 1}], "/v3/projects/1/trackers": [{"id": n} for n in range(1, 4)],
                         **{f"/v3/trackers/{n}/fields": [{"id": 3}] for n in range(1, 4)},
                         **{f"/v3/trackers/{n}/items": {"page": 1, "total": 0, "pageSize": 100, "itemRefs": []} for n in range(1, 4)}})
    c = CodebeamerConnector(client)
    c.probe(); c.list_projects(); c.list_scopes("1")
    c.list_fields("1", ["1", "2", "3"]); list(c.iter_refs("1", ["1", "2", "3"]))
    paths = [call[1] for call in client.calls]
    assert paths.count("/v3/projects") == 1 and paths.count("/v3/projects/1/trackers") == 1
