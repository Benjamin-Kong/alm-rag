# M2 connector TDD evidence

Observed 2026-10-20, isolated checkout `.worktrees/m2-connectors`. Sources are synthetic; no actual ALM socket, credential, dump or attachment was used. Owned paths: `src/almrag/connectors/**`, `tests/test_connectors.py`, `tests/fixtures/alm/**`, this document. No source writes or Git remote operations.

## Actual executions

All commands used Main's existing Python interpreter with this checkout's `src` selected by pytest's `pythonpath` configuration:

`/Users/skongby/projects/alm-rag/.venv/bin/python -m pytest tests/test_connectors.py -q`

1. **RED observed** before adapter implementation: exit2, collection error `ModuleNotFoundError: No module named 'almrag.connectors'` (0.15s). Twenty-one parametrized contract cases were already written.
2. First implementation: exit1, 18 passed /3 failed. The three failures exposed FakeClient responses lacking httpx Request objects, so `raise_for_status` could not run. Corrected the fake response contract to include Request; did not remove the status check.
3. **GREEN observed**: exit0, **21 passed** (0.08s).
4. Added official-contract regression tests first: **RED observed**, exit1, **4 failed /24 passed** (0.14s). Failures: CB attachment route, Polarion top-level resource revision and duplicate catalog identities for both sources.
5. Minimum fixes: use documented CB `/v3/attachments/{id}/content`, preserve resource `revision` and reject duplicate identities. **GREEN observed**, exit0, **28 passed** (0.10s).
6. Added six complete synthetic project-matrix cases (three per product), exercising scopes, fields, refs, full item and attachment bytes. **GREEN observed**, exit0, **34 passed** (0.11s).
7. Regression command `/Users/skongby/projects/alm-rag/.venv/bin/python -m pytest -q`: **PASS**, exit0, **72 passed** (3.72s). One existing Starlette TestClient/httpx deprecation warning; no skipped/xfail cases.

## Coverage and contract

| Requirement | Observed synthetic evidence |
|---|---|
| SRS-001/045 | Accessible-project discovery, three projects per product, read-only probe, sanitized HTTP403 failure |
| SRS-003/046/047 | CB tracker instance ID distinct from tracker type; Polarion enumeration options; selected-scope catalog revalidation; field metadata |
| SRS-004/049 | Complete raw payload, unknown/custom attributes, nested CB table values, Unicode and large HTML retained without truncation |
| SRS-005/053 | Only injected bounded client requests download exact attachment bytes; filenames never become local paths; forged request path rejected |
| SRS-006/007 | Latest-only refs; absent Polarion revision stays null; observed revision preserved; bounded pages, repeated page/duplicate ID/partial page fail globally |
| SRS-008 | HTTP404 remains ambiguous isolated error; no deletion inferred from absence; explicit source boolean is preserved |
| SRS-010 | Raw HTML retained; unverified CB Wiki POST blocked with diagnostic; explicitly verified renderer uses documented TRACKER_ITEM body; Polarion original rich text retained |
| SRS-022 | CB references/associations and Polarion forward/backlink resource normalization; referenced targets never crawled |
| SRS-058 | Actual Red/Green observations above |

Public contract: `CodebeamerConnector(client, renderer_verified=False)` and `PolarionConnector(client, renderer_verified=False)`, each exposing `probe`, `list_projects`, `list_scopes`, `list_fields`, `iter_refs`, `get_item`, `download_attachment`. `ConnectorError` exposes sanitized `code` and `global_error`.

## Integration correction observations

Main integration review identified that shared `AlmError` and `LeaseLost` inherit `ValueError`. The original generic JSON-error branch therefore misclassified control failures and lost PAUSED/auth metadata.

- Added transport-bridge cases for429 pause,401 global authentication,403 isolated permission, circuit-open pause and lease revocation. Actual **RED**: **5 failed /34 passed** (0.19s).
- Preserve sanitized `code`, `global_error`, `stop_state`, `retryable`, `status`; propagate the exact `LeaseLost` instance. Actual **GREEN**: **39 passed** (0.09s).
- Main authorized an explicit normalized-field namespace for default policy. Added property tests first. Actual **RED**: **2 failed /39 passed** (0.16s), missing `normalized_fields` property.
- Added `normalized_fields = ('title', 'description')`. These identify normalized envelope properties, never source IDs; `list_fields()` keeps original numeric/string IDs untouched. Main owns union validation and separate public catalog representation.
- Final isolated regression: **79 passed** (3.68s), one existing Starlette/httpx deprecation warning, no skip/xfail. Connector cases now total41. Main's integrated tests must still be run after copying these changes.

`client.get_json(path, params=None)` and `client.request(method, path, params=None, json=None, max_bytes=None)` are the only transport entry points. Adapters never construct httpx.Client. Pagination uses checked numeric parameters instead of requesting a response-provided next link. Main transport owns shared server throttling/retry/origin/security limits; adapter unit tests do not claim those integration tests passed.

Item `raw` is the unchanged complete item response. `raw_resources` separately retains full relation/attachment entries. Normalized fields retain standard/unknown source attributes as JSON and CB custom field values with their original type; source payload metadata remains recoverable from `raw`. No original resource is rewritten.

## Official reference evidence and limits

- [PTC tracker item model](https://support.ptc.com/help/codebeamer/r3.1/en/codebeamer/developers_guide/swagger/dg_tracker_item_model_structure.html): explicit built-ins and `customFields` carry distinct source representations, including nested table values.
- [PTC tracker information](https://support.ptc.com/help/codebeamer/r3.1/en/codebeamer/developers_guide/swagger/SwaggerV3_TrackerInformation.html): tracker instance field discovery.
- [PTC tracker item operations](https://support.ptc.com/help/codebeamer/r2.1/en/codebeamer/developers_guide/11375769.html): itemRefs paging and relations endpoint; certain resource lists historically expose single-page metadata. This older reference does not establish current live compatibility.
- [PTC Server Guide r3.1](https://support.ptc.com/help/codebeamer/r3.1/en/codebeamer/cb_dpt_integration/26334048.html): attachment bytes use `GET /v3/attachments/{attachmentId}/content`.
- [PTC Wiki information](https://support.ptc.com/help/codebeamer/r3.1/en/codebeamer/developers_guide/swagger/26023354.html): renderer request shape. Documentation alone does not enable a live profile or prove server-side safety.
- [Siemens advanced concepts](https://developer.siemens.com/polarion/latest/advanced-concepts.html): type enumeration options, project `getFieldsMetadata`, forward/backlink and attachment resources. Backlink behavior differs across versions; candidate adapter uses dedicated backlink endpoint, not included relationships.
- [Siemens basic concepts](https://developer.siemens.com/polarion/2512/basic-concepts.html): JSON:API resource identity/revision and numeric paging with next link/totalCount.
- [Siemens known limitations](https://developer.siemens.com/polarion/latest/limitations-and-known-issues.html): specific HEAD revision and processed rich text HTML may be unavailable. No revision is fabricated; rich text HTML is original source, not a claim of browser-equivalent rendering.

**NOT VERIFIED:** live source API version/configuration compatibility, credential/permission catalogs, server renderer non-mutating behavior, actual frontend display fidelity, simultaneous source edits during detail/relationship reads, production source limits, and source history before initial observation. Source changes that alter totals/duplicate identities fail the current scan; stable immutable server snapshots require a compatible source contract. Main's pipeline owns hash/delta persistence, atomic storage and failure replay.
