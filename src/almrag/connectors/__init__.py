"""Read-only, injected-transport ALM product adapters.

These adapters never instantiate clients or follow links from source content.
The injected shared transport owns origin checks, credentials, pacing and retries.
"""
from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
import json
import time
from typing import Any, Iterator
from urllib.parse import parse_qs, quote, urlsplit

import httpx
from almrag.queue import LeaseLost

PAGE_SIZE = 100
MAX_PAGES = 10000
MAX_ATTACHMENT_BYTES = 100 * 1024 * 1024
MAX_RENDER_BYTES = 16 * 1024 * 1024
CATALOG_MEMO_SECONDS = 300


class ConnectorError(Exception):
    """Stable diagnostic only: never include source bodies, URLs or credentials."""

    def __init__(self, code: str, global_error: bool = False, *, stop_state: str = "BLOCKED",
                 retryable: bool = False, status: int | None = None):
        # Accept only stable codes even if a caller passes an unsafe message.
        safe = code if code and all(c.isupper() or c.isdigit() or c == "_" for c in code) else "CONNECTOR_ERROR"
        super().__init__(safe)
        self.code = safe
        self.global_error = global_error
        self.stop_state = stop_state if stop_state in {"PAUSED", "BLOCKED", "FAILED", "CANCELLED"} else "BLOCKED"
        self.retryable = bool(retryable)
        self.status = status if isinstance(status, int) and not isinstance(status, bool) else None


def _segment(value: Any) -> str:
    value = str(value)
    if not value or value in (".", "..") or any(c in value for c in "/\\%?#\x00\r\n"):
        raise ConnectorError("INVALID_SOURCE_ID", global_error=True)
    return quote(value, safe="-_.~")


def _id(value: Any) -> str:
    if value is None or isinstance(value, (bool, dict, list)) or str(value) == "":
        raise ConnectorError("INVALID_SOURCE_PAYLOAD", global_error=True)
    return str(value)


def _revision(value: Any) -> str | None:
    return None if value is None else _id(value)


def _dict(value: Any) -> dict:
    if not isinstance(value, dict):
        raise ConnectorError("INVALID_SOURCE_PAYLOAD", global_error=True)
    return value


def _list(value: Any) -> list:
    if not isinstance(value, list) or any(not isinstance(v, dict) for v in value):
        raise ConnectorError("INVALID_SOURCE_PAYLOAD", global_error=True)
    return value


def _unique(values: list, seen_ids: set) -> None:
    for value in values:
        source_id = value.get("id", value.get("fieldId"))
        if source_id is not None:
            source_id = _id(source_id)
            if source_id in seen_ids:
                raise ConnectorError("PAGINATION_DUPLICATE_ITEM", True)
            seen_ids.add(source_id)


def _polarion_revision(resource: dict) -> str | None:
    attrs = _dict(resource.get("attributes", {}))
    return _revision(resource.get("revision", attrs.get("revision", _dict(resource.get("meta", {})).get("revision"))))


@contextmanager
def _item_conversion():
    """Only pure conversion of one identified Item may downgrade shape errors.

    Network, identity/catalog validation and pagination must stay outside this
    context. Never downgrade arbitrary ConnectorError or control exceptions.
    """
    try:
        yield
    except ConnectorError as error:
        if error.code not in {"INVALID_SOURCE_PAYLOAD", "INVALID_RELATION_PAYLOAD"}:
            raise
        raise ConnectorError("ITEM_NORMALIZATION_ERROR", global_error=False) from None
    except (LeaseLost, OSError):
        raise
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        if hasattr(error, "code"):
            raise
        raise ConnectorError("ITEM_NORMALIZATION_ERROR", global_error=False) from None


def _description(source_format: Any, raw: Any) -> dict:
    if not isinstance(source_format, str) or (raw is not None and not isinstance(raw, str)):
        raise ValueError("invalid description representation")
    description = {"format": source_format, "raw": raw}
    if source_format.lower() in {"html", "text/html"}:
        description["html"] = raw
    return description


class _Connector:
    # These name envelope properties, never fabricated source field identities.
    # Source catalogs retain their original field IDs in list_fields().
    normalized_fields = ("title", "description")

    def __init__(self, client, renderer_verified: bool = False):
        self.client = client
        self.renderer_verified = renderer_verified
        self._catalog_memo = {}

    def _memo(self, key, fetch):
        # One operation (probe/preflight/discovery) otherwise re-lists the same catalog
        # several times; with many trackers that is thousands of throttled requests.
        hit = self._catalog_memo.get(key)
        if hit is None or time.monotonic() - hit[0] >= CATALOG_MEMO_SECONDS:
            hit = self._catalog_memo[key] = (time.monotonic(), fetch())
        return deepcopy(hit[1])

    def _call(self, action, *args, **kwargs):
        try:
            return action(*args, **kwargs)
        except (ConnectorError, LeaseLost):
            raise
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            raise ConnectorError(f"HTTP_{status}", global_error=status == 401, status=status) from None
        except httpx.HTTPError:
            raise ConnectorError("TRANSPORT_ERROR", global_error=True) from None
        except Exception as exc:
            # Shared transport errors already carry sanitized codes and scope.
            # AlmError and LeaseLost inherit ValueError; inspect known control
            # metadata before classifying ordinary JSON decoding/shape failures.
            if hasattr(exc, "code"):
                raise ConnectorError(str(exc.code), bool(getattr(exc, "global_error", True)),
                                     stop_state=getattr(exc, "stop_state", "BLOCKED"),
                                     retryable=getattr(exc, "retryable", False),
                                     status=getattr(exc, "status", None)) from None
            if isinstance(exc, (ValueError, TypeError, KeyError)):
                raise ConnectorError("INVALID_SOURCE_PAYLOAD", global_error=True) from None
            raise

    def _get(self, path: str, params: dict | None = None):
        return self._call(self.client.get_json, path, params=params)

    def _request(self, method: str, path: str, **kwargs):
        response = self._call(self.client.request, method, path, **kwargs)
        self._call(response.raise_for_status)
        return response

    def _url(self, path: str) -> str:
        base = str(getattr(self.client, "base_url", "")).rstrip("/")
        return base + path

    def _selected(self, project_id, scope_ids):
        scopes = self.list_scopes(project_id)
        available = {s["id"] for s in scopes}
        selected = available if scope_ids is None else {_id(s) for s in scope_ids}
        if not selected <= available:
            raise ConnectorError("INVALID_SCOPE_SELECTION", global_error=True)
        return [s["id"] for s in scopes if s["id"] in selected]

    def download_attachment(self, project_id, item_id, attachment) -> bytes:
        # Reconstruct the exact path; never request an attachment's supplied URL.
        path = self._attachment_path(project_id, item_id, _id(attachment["id"]))
        if attachment.get("path") != path:
            raise ConnectorError("INVALID_ATTACHMENT_PATH", global_error=True)
        response = self._request("GET", path, max_bytes=MAX_ATTACHMENT_BYTES)
        if len(response.content) > MAX_ATTACHMENT_BYTES:
            raise ConnectorError("ATTACHMENT_TOO_LARGE")
        return response.content


class CodebeamerConnector(_Connector):
    """Candidate Codebeamer REST v3 profile; latest observed revisions only."""

    def _pages(self, path: str, keys: tuple[str, ...]) -> Iterator[dict]:
        seen: set[str] = set()
        seen_ids: set[str] = set()
        expected_total = None
        count = 0
        for page in range(1, MAX_PAGES + 1):
            payload = self._get(path, {"page": page, "pageSize": PAGE_SIZE})
            if isinstance(payload, list):
                if page != 1:
                    raise ConnectorError("PAGINATION_INVALID", True)
                values = _list(payload)
                _unique(values, seen_ids)
                yield from values
                return
            payload = _dict(payload)
            key = next((k for k in keys if k in payload), None)
            if key is None:
                raise ConnectorError("INVALID_SOURCE_PAYLOAD", True)
            values = _list(payload[key])
            total = payload.get("total")
            size = payload.get("pageSize", PAGE_SIZE)
            if payload.get("page", page) != page:
                raise ConnectorError("PAGINATION_REPEATED_PAGE", True)
            if not isinstance(size, int) or isinstance(size, bool) or size < 0:
                raise ConnectorError("PAGINATION_INVALID", True)
            if total is not None:
                if not isinstance(total, int) or isinstance(total, bool) or total < 0:
                    raise ConnectorError("PAGINATION_INVALID", True)
                if expected_total is not None and total != expected_total:
                    raise ConnectorError("PAGINATION_CHANGED_TOTAL", True)
                expected_total = total
            signature = json.dumps(values, sort_keys=True, ensure_ascii=False)
            if values and signature in seen:
                raise ConnectorError("PAGINATION_REPEATED_PAGE", True)
            seen.add(signature)
            _unique(values, seen_ids)
            count += len(values)
            if total is not None and count > total:
                raise ConnectorError("PAGINATION_INVALID", True)
            yield from values
            if total is not None and count == total:
                return
            if not values:
                if total is not None and count < total:
                    raise ConnectorError("PAGINATION_INCOMPLETE", True)
                return
            if total is None and len(values) < size:
                return
        raise ConnectorError("PAGINATION_LIMIT", True)

    def probe(self) -> dict:
        projects = self.list_projects()
        return {"source_type": "codebeamer", "api_profile": "cb-rest-v3", "read_only": True,
                "project_count": len(projects), "revision_history": "latest_observed",
                "wiki_renderer": "VERIFIED" if self.renderer_verified else "UNVERIFIED",
                "server_compatibility": "NOT_VERIFIED"}

    def list_projects(self) -> list[dict]:
        return self._memo(("projects",), self._fetch_projects)

    def _fetch_projects(self) -> list[dict]:
        return [{"id": _id(p.get("id")), "name": p.get("name", str(p.get("id"))),
                 "url": p.get("url") or self._url(f"/v3/projects/{_segment(p.get('id'))}")}
                for p in self._pages("/v3/projects", ("projects", "references", "items"))]

    def list_scopes(self, project_id) -> list[dict]:
        return self._memo(("scopes", str(project_id)), lambda: self._fetch_scopes(project_id))

    def _fetch_scopes(self, project_id) -> list[dict]:
        path = f"/v3/projects/{_segment(project_id)}/trackers"
        return [{"id": _id(s.get("id")), "name": s.get("name", str(s.get("id"))), "kind": "TRACKER"}
                for s in self._pages(path, ("trackers", "references", "items"))]

    def list_fields(self, project_id, scope_ids=None) -> list[dict]:
        fields = []
        for scope in self._selected(project_id, scope_ids):
            for f in self._pages(f"/v3/trackers/{_segment(scope)}/fields", ("fields", "references", "items")):
                fields.append({**deepcopy(f), "id": _id(f.get("id", f.get("fieldId"))),
                               "name": f.get("name", str(f.get("id", f.get("fieldId")))), "scope_id": scope})
        return fields

    def iter_refs(self, project_id, scope_ids=None) -> Iterator[dict]:
        seen = set()
        for scope in self._selected(project_id, scope_ids):
            for ref in self._pages(f"/v3/trackers/{_segment(scope)}/items", ("itemRefs", "items")):
                item_id = _id(ref.get("id"))
                if item_id in seen:
                    raise ConnectorError("PAGINATION_DUPLICATE_ITEM", True)
                seen.add(item_id)
                yield {"id": item_id, "scope_id": scope, "revision": _revision(ref.get("version")),
                       "modified": ref.get("modifiedAt")}

    def _attachment_path(self, project_id, item_id, attachment_id):
        _segment(project_id)
        _segment(item_id)
        return f"/v3/attachments/{_segment(attachment_id)}/content"

    def get_item(self, project_id, item_id) -> dict:
        project = _segment(project_id)
        item = _segment(item_id)
        raw = _dict(self._get(f"/v3/items/{item}"))
        if _id(raw.get("id")) != str(item_id):
            raise ConnectorError("ITEM_ID_MISMATCH", True)
        # Scope and revision are integrity checks, outside local conversion.
        scope_id = _id(_dict(raw.get("tracker")).get("id"))
        revision = _revision(raw.get("version"))
        with _item_conversion():
            description = _description(raw.get("descriptionFormat", "PlainText"), raw.get("description", ""))
            fields = [{"source_field_id": k, "name": k, "source_format": "JSON", "raw_value": deepcopy(v)}
                      for k, v in raw.items() if k != "customFields"]
            for field in _list(raw.get("customFields", [])):
                fields.append({"source_field_id": _id(field.get("fieldId")), "name": field.get("name", str(field.get("fieldId"))),
                               "source_format": field.get("type", "JSON"),
                               "raw_value": deepcopy(field.get("value", field.get("values")))})
            json.dumps(fields, allow_nan=False)
        diagnostics = []
        if description["format"].lower() in ("wiki", "wikitext"):
            if self.renderer_verified:
                response = self._request("POST", f"/v3/projects/{project}/wiki2html", json={
                    "contextId": raw["id"], "contextVersion": raw.get("version"),
                    "markup": description["raw"], "renderingContextType": "TRACKER_ITEM"}, max_bytes=MAX_RENDER_BYTES)
                if len(response.content) > MAX_RENDER_BYTES:
                    raise ConnectorError("RENDER_TOO_LARGE")
                description["html"] = response.text
            else:
                diagnostics.append("WIKI_RENDERER_UNVERIFIED")
        relation_raw = self._get(f"/v3/items/{item}/relations")
        with _item_conversion():
            relation_raw = _dict(relation_raw)
            relations = []
            for group in ("downstreamReferences", "upstreamReferences", "incomingAssociations", "outgoingAssociations"):
                for relation in _list(relation_raw.get(group, [])):
                    target = relation.get("itemRevision", relation.get("item", relation.get("target")))
                    target = _dict(target)
                    kind = relation.get("type", group)
                    if isinstance(kind, dict):
                        kind = kind.get("name", kind.get("id", group))
                    relations.append({"type": str(kind), "target_id": _id(target.get("id"))})
        attachment_raw = list(self._pages(f"/v3/items/{item}/attachments", ("attachments", "items")))
        attachments = []
        for attachment in attachment_raw:
            aid = _id(attachment.get("id"))
            path = self._attachment_path(project_id, item_id, aid)
            attachments.append({"id": aid, "filename": attachment.get("name", attachment.get("fileName", aid)),
                                "path": path, "source_url": self._url(path)})
        return {"id": _id(raw["id"]), "project_id": str(project_id), "scope_id": scope_id,
                "revision": revision, "modified": raw.get("modifiedAt"), "title": raw.get("name", ""),
                "description": description, "fields": fields, "raw": deepcopy(raw), "relations": relations,
                "attachments": attachments, "source_url": raw.get("url") or self._url(f"/v3/items/{item}"),
                "deleted": raw.get("deleted") is True, "diagnostics": diagnostics,
                "raw_resources": {"relations": relation_raw, "attachments": attachment_raw}}


class PolarionConnector(_Connector):
    """Candidate Polarion REST v1 JSON:API profile; no LiveDoc traversal."""

    def _pages(self, path: str, params: dict | None = None) -> Iterator[dict]:
        seen = set()
        seen_ids = set()
        count = 0
        expected_total = None
        for page in range(1, MAX_PAGES + 1):
            payload = _dict(self._get(path, {**(params or {}), "page[number]": page, "page[size]": PAGE_SIZE}))
            values = _list(payload.get("data"))
            signature = json.dumps(values, sort_keys=True, ensure_ascii=False)
            if values and signature in seen:
                raise ConnectorError("PAGINATION_REPEATED_PAGE", True)
            seen.add(signature)
            _unique(values, seen_ids)
            count += len(values)
            meta = _dict(payload.get("meta", {}))
            total = meta.get("totalCount", meta.get("total"))
            if total is not None:
                if not isinstance(total, int) or isinstance(total, bool) or total < 0 or count > total:
                    raise ConnectorError("PAGINATION_INVALID", True)
                if expected_total is not None and total != expected_total:
                    raise ConnectorError("PAGINATION_CHANGED_TOTAL", True)
                expected_total = total
            yield from values
            next_link = _dict(payload.get("links", {})).get("next")
            if not next_link:
                if expected_total is not None and count != expected_total:
                    raise ConnectorError("PAGINATION_INCOMPLETE", True)
                return
            if not values:
                raise ConnectorError("PAGINATION_INCOMPLETE", True)
            if isinstance(next_link, dict):
                next_link = next_link.get("href")
            if not isinstance(next_link, str):
                raise ConnectorError("PAGINATION_INVALID", True)
            link = urlsplit(next_link)
            # Use only the checked numeric page, never the source-supplied URL.
            query = parse_qs(link.query)
            if query.get("page[number]") != [str(page + 1)]:
                raise ConnectorError("PAGINATION_REPEATED_PAGE", True)
            if link.path != path and not link.path.endswith("/rest/v1" + path):
                raise ConnectorError("PAGINATION_INVALID", True)
        raise ConnectorError("PAGINATION_LIMIT", True)

    def probe(self) -> dict:
        projects = self.list_projects()
        return {"source_type": "polarion", "api_profile": "polarion-rest-v1", "read_only": True,
                "project_count": len(projects), "revision_history": "latest_observed",
                "processed_html": "UNSUPPORTED", "server_compatibility": "NOT_VERIFIED"}

    def list_projects(self) -> list[dict]:
        return self._memo(("projects",), self._fetch_projects)

    def _fetch_projects(self) -> list[dict]:
        projects = []
        for project in self._pages("/projects", {"fields[projects]": "@all"}):
            pid = _id(project.get("id"))
            attrs = _dict(project.get("attributes", {}))
            projects.append({"id": pid, "name": attrs.get("name", pid),
                             "url": _dict(project.get("links", {})).get("self") or self._url(f"/projects/{_segment(pid)}")})
        return projects

    def list_scopes(self, project_id) -> list[dict]:
        return self._memo(("scopes", str(project_id)), lambda: self._fetch_scopes(project_id))

    def _fetch_scopes(self, project_id) -> list[dict]:
        payload = _dict(self._get(f"/projects/{_segment(project_id)}/enumerations/~/workitem-type/~"))
        options = _list(_dict(_dict(payload.get("data")).get("attributes")).get("options"))
        return [{"id": _id(o.get("id")), "name": o.get("name", str(o.get("id"))), "kind": "WORK_ITEM_TYPE"} for o in options]

    def list_fields(self, project_id, scope_ids=None) -> list[dict]:
        fields = []
        for scope in self._selected(project_id, scope_ids):
            payload = _dict(self._get(f"/projects/{_segment(project_id)}/actions/getFieldsMetadata",
                                     {"resourceType": "workitems", "targetType": scope}))
            attrs = _dict(_dict(payload.get("data")).get("attributes"))
            for fid, field in attrs.items():
                field = _dict(field)
                fields.append({**deepcopy(field), "id": fid, "name": field.get("label", fid), "scope_id": scope})
        return fields

    def _local_item_id(self, project_id, resource):
        source_id = _id(resource.get("id"))
        attrs = _dict(resource.get("attributes", {}))
        local_id = attrs.get("id", source_id.removeprefix(str(project_id) + "/"))
        if source_id not in (str(local_id), str(project_id) + "/" + str(local_id)):
            raise ConnectorError("ITEM_PROJECT_MISMATCH", True)
        _segment(local_id)
        return str(local_id)

    def iter_refs(self, project_id, scope_ids=None) -> Iterator[dict]:
        selected = set(self._selected(project_id, scope_ids))
        seen = set()
        for item in self._pages(f"/projects/{_segment(project_id)}/workitems", {"fields[workitems]": "@all", "sort": "id"}):
            attrs = _dict(item.get("attributes", {}))
            scope = _id(attrs.get("type"))
            item_id = self._local_item_id(project_id, item)
            if item_id in seen:
                raise ConnectorError("PAGINATION_DUPLICATE_ITEM", True)
            seen.add(item_id)
            if scope in selected:
                yield {"id": item_id, "scope_id": scope,
                       "revision": _polarion_revision(item),
                       "modified": attrs.get("updated")}

    def _attachment_path(self, project_id, item_id, attachment_id):
        return f"/projects/{_segment(project_id)}/workitems/{_segment(item_id)}/attachments/{_segment(attachment_id)}/content"

    def get_item(self, project_id, item_id) -> dict:
        path = f"/projects/{_segment(project_id)}/workitems/{_segment(item_id)}"
        raw = _dict(self._get(path, {"fields[workitems]": "@all"}))
        resource = _dict(raw.get("data"))
        if self._local_item_id(project_id, resource) != str(item_id):
            raise ConnectorError("ITEM_ID_MISMATCH", True)
        attrs = _dict(resource.get("attributes"))
        scope_id = _id(attrs.get("type"))
        revision = _polarion_revision(resource)
        with _item_conversion():
            rich = attrs.get("description", "")
            if isinstance(rich, dict):
                description = _description(rich.get("type", "text/plain"), deepcopy(rich.get("value", "")))
            else:
                description = _description("text/plain", deepcopy(rich))
            fields = [{"source_field_id": k, "name": k,
                       "source_format": v.get("type", "JSON") if isinstance(v, dict) else "JSON", "raw_value": deepcopy(v)}
                      for k, v in attrs.items()]
            json.dumps(fields, allow_nan=False)
        relation_raw = {}
        relations = []
        for endpoint in ("linkedworkitems", "backlinkedworkitems"):
            entries = list(self._pages(path + "/" + endpoint, {f"fields[{endpoint}]": "@all"}))
            relation_raw[endpoint] = entries
            with _item_conversion():
                for relation in entries:
                    relattrs = _dict(relation.get("attributes", {}))
                    relationships = _dict(relation.get("relationships", {}))
                    target = _dict(_dict(relationships.get("workItem", {})).get("data", {})).get("id")
                    if target is None:
                        raise ConnectorError("INVALID_RELATION_PAYLOAD", True)
                    relations.append({"type": str(relattrs.get("role", endpoint)), "target_id": _id(target)})
        attachment_raw = list(self._pages(path + "/attachments", {"fields[attachments]": "@all"}))
        attachments = []
        for attachment in attachment_raw:
            source_id = _id(attachment.get("id"))
            aid = source_id.removeprefix(f"{project_id}/{item_id}/")
            attrs_attachment = _dict(attachment.get("attributes", {}))
            apath = self._attachment_path(project_id, item_id, aid)
            attachments.append({"id": aid, "filename": attrs_attachment.get("fileName", attrs_attachment.get("title", aid)),
                                "path": apath, "source_url": self._url(apath)})
        return {"id": str(item_id), "project_id": str(project_id), "scope_id": scope_id,
                "revision": revision,
                "modified": attrs.get("updated"), "title": attrs.get("title", ""), "description": description,
                "fields": fields, "raw": deepcopy(raw), "relations": relations, "attachments": attachments,
                "source_url": _dict(resource.get("links", {})).get("self") or self._url(path),
                "deleted": attrs.get("deleted") is True, "diagnostics": ["POLARION_PROCESSED_HTML_UNAVAILABLE"],
                "raw_resources": {"relations": relation_raw, "attachments": attachment_raw}}


__all__ = ["CodebeamerConnector", "PolarionConnector", "ConnectorError"]
