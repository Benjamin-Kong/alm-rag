"""SRS-004/055 OI-038: actual product adapters and collection failure isolation."""
from copy import deepcopy
import json

import pytest

from almrag.alm_http import AlmError
from almrag.collection import CollectionService
from almrag.connectors import CodebeamerConnector, PolarionConnector
from almrag.queue import LeaseLost, Queue
from almrag.storage import Database
from test_connectors import cb_item_client, polarion_client


def source_fixture(product):
    if product == "codebeamer":
        client = cb_item_client()
        project, first, second, field = "1", "100", "101", "900"
        for suffix in ("", "/relations", "/attachments"):
            client.routes["/v3/items/101" + suffix] = deepcopy(client.routes["/v3/items/100" + suffix])
        client.routes["/v3/items/101"]["id"] = 101
        client.routes["/v3/items/101/relations"] = {}
        client.routes["/v3/items/100/attachments"] = []
        client.routes["/v3/items/101/attachments"] = []
        client.routes.update({"/v3/projects": [{"id": 1}], "/v3/projects/1/trackers": [{"id": 31}],
            "/v3/trackers/31/fields": [{"id": 900, "name": "Custom table"}],
            "/v3/trackers/31/items": {"total": 2, "itemRefs": [{"id": 100}, {"id": 101}]}})
        adapter = CodebeamerConnector(client)
        paths = ("/v3/items/100", "/v3/items/101")
    else:
        client = polarion_client()
        project, first, second, field = "p", "REQ-1", "REQ-2", "futureCustom"
        for suffix in ("", "/linkedworkitems", "/backlinkedworkitems", "/attachments"):
            client.routes["/projects/p/workitems/REQ-2" + suffix] = deepcopy(client.routes["/projects/p/workitems/REQ-1" + suffix])
        client.routes["/projects/p/workitems/REQ-2"]["data"]["id"] = "p/REQ-2"
        client.routes["/projects/p/workitems/REQ-2"]["data"]["attributes"]["id"] = "REQ-2"
        client.routes["/projects/p/workitems/REQ-1/attachments"] = {"data": []}
        client.routes["/projects/p/workitems/REQ-2/attachments"] = {"data": []}
        client.routes.update({"/projects": {"data": [{"id": "p"}]},
            "/projects/p/enumerations/~/workitem-type/~": {"data": {"attributes": {"options": [{"id": "requirement"}]}}},
            "/projects/p/actions/getFieldsMetadata": {"data": {"attributes": {"futureCustom": {"label": "Custom"}}}},
            "/projects/p/workitems": {"data": [{"id": "p/REQ-1", "attributes": {"type": "requirement"}},
                                               {"id": "p/REQ-2", "attributes": {"type": "requirement"}}]}})
        adapter = PolarionConnector(client)
        paths = ("/projects/p/workitems/REQ-1", "/projects/p/workitems/REQ-2")
    return client, adapter, project, first, second, field, paths


def prepared(tmp_path, product):
    client, adapter, project, first, second, field, paths = source_fixture(product)
    db = Database(tmp_path / "data.sqlite")
    db.migrate()
    instance = db.add_instance(product, "https://alm.example.invalid", "Synthetic", "env:FIXTURE")
    service = CollectionService(db, lambda _: adapter, tmp_path / "assets")
    project_uid = service.configure_project(instance, project, "Synthetic", embedding_fields=[field],
        scope_kind="TRACKER" if product == "codebeamer" else "WORK_ITEM_TYPE")
    assert service.preflight(project_uid)["status"] == "READY"
    service.enqueue(project_uid)
    job = Queue(db).claim("fixture", 300)
    return client, adapter, db, service, job, first, second, paths


@pytest.mark.parametrize("product", ["codebeamer", "polarion"])
@pytest.mark.parametrize("malformation", ["fields", "description", "relations"])
def test_srs_055_malformed_item_is_queued_and_good_sibling_collected(tmp_path, product, malformation):
    client, adapter, db, service, job, first, second, paths = prepared(tmp_path, product)
    raw = client.routes[paths[0]]
    if product == "codebeamer":
        if malformation == "fields":
            raw["customFields"] = {"invalid": "expected a field list"}
        elif malformation == "description":
            raw["descriptionFormat"] = ["invalid"]
        else:
            client.routes[paths[0] + "/relations"] = {"outgoingAssociations": [{"type": "depends"}]}
    else:
        if malformation == "fields":
            raw["data"]["attributes"]["futureCustom"] = float("nan")
        elif malformation == "description":
            raw["data"]["attributes"]["description"] = {"type": "text/html", "value": ["invalid text"]}
        else:
            client.routes[paths[0] + "/linkedworkitems"] = {"data": [{"id": "badrelation", "attributes": {"role": "parent"}}]}
    good_raw = deepcopy(client.routes[paths[1]])
    assert service.run(job) == "COMPLETED_WITH_ERRORS"
    final = Queue(db).get_job(job["job_id"])
    assert (final["progress_total"], final["succeeded_items"], final["failed_items"]) == (2, 1, 1)
    assert [path for method, path, _ in client.calls if method == "GET" and path in paths] == list(paths)
    with db.connect() as connection:
        failure = connection.execute("SELECT * FROM collection_failures").fetchall()
        assert len(failure) == 1 and failure[0]["source_item_id"] == first
        assert failure[0]["revision_uid"] is None and failure[0]["error_code"] == "ITEM_NORMALIZATION_ERROR"
        rows = connection.execute("SELECT raw_payload FROM item_revisions").fetchall()
        assert len(rows) == 1
        envelope = json.loads(rows[0]["raw_payload"])
        assert envelope["id"] == second and envelope["raw"] == good_raw
        assert connection.execute("SELECT count(*) FROM items WHERE active_revision_uid IS NOT NULL").fetchone()[0] == 0


@pytest.mark.parametrize("product", ["codebeamer", "polarion"])
@pytest.mark.parametrize("code,state,status", [("UNAUTHORIZED", "BLOCKED", 401),
    ("SERVER_PAUSED", "PAUSED", 429), ("CIRCUIT_OPEN", "PAUSED", None), ("STORAGE_ERROR", "BLOCKED", None)])
def test_srs_054_global_control_failure_stops_good_sibling(tmp_path, product, code, state, status):
    client, adapter, db, service, job, first, second, paths = prepared(tmp_path, product)
    client.routes[paths[0]] = AlmError(code, True, stop_state=state, status=status)
    assert service.run(job) == state
    final = Queue(db).get_job(job["job_id"])
    assert final["last_error_code"] == code
    assert final["succeeded_items"] == final["failed_items"] == 0
    assert paths[1] not in [path for _, path, _ in client.calls]
    with db.connect() as connection:
        assert connection.execute("SELECT count(*) FROM collection_failures").fetchone()[0] == 0


@pytest.mark.parametrize("product", ["codebeamer", "polarion"])
def test_srs_055_identity_mismatch_remains_global(tmp_path, product):
    client, adapter, db, service, job, first, second, paths = prepared(tmp_path, product)
    raw = client.routes[paths[0]]
    if product == "codebeamer":
        raw["id"] = 999
    else:
        raw["data"]["id"] = "different/REQ-1"
    assert service.run(job) == "BLOCKED"
    assert paths[1] not in [path for _, path, _ in client.calls]
    assert Queue(db).get_job(job["job_id"])["failed_items"] == 0


@pytest.mark.parametrize("product", ["codebeamer", "polarion"])
def test_srs_055_lease_revocation_remains_exact_exception(tmp_path, product):
    client, adapter, db, service, job, first, second, paths = prepared(tmp_path, product)
    revoked = LeaseLost("synthetic revoked lease")
    client.routes[paths[0]] = revoked
    with pytest.raises(LeaseLost) as caught:
        service.run(job)
    assert caught.value is revoked
    assert paths[1] not in [path for _, path, _ in client.calls]
