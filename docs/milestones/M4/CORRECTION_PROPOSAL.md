# M4 OI-049 correction proposal — pending human approval

2026-10-20. Status HUMAN_REVIEW_REQUIRED. No correction has been implemented.

Independent QA reproduced a missing SRS-018 capability: a published Item with source_item_id `ALM-EXACT-987654`, title `Brake torque requirement`, description `Torque limits` cannot be found through the keyword channel by its exact original ID. ID is absent from chunk text and keyword terms. SearchRequest accepts no ID filter and rejects a proposed `filters.source_item_id` field. Dense similarity is not proof of exact ID support. See SRS.md SRS-018 and SRS-009; the draft OpenAPI also omits this capability and cannot override SRS.

## Bounded proposed correction

1. Freeze an explicit typed exact-ID and metadata-filter contract in DESIGN/OpenAPI before implementation. At minimum support exact original source Item ID and internal Item UID within mandatory authorized project scope, plus existing project and discovered scope ID filters. Preserve original case-sensitive source identity; do not infer IDs from body hyperlinks. Review SRS-009 field-filter obligations against preserved normalized/custom fields, and explicitly document supported equality semantics; do not invent advanced filter operators.
2. Keep ID/metadata separate from embedding input. Add a deterministic authorized exact-ID retrieval path and version keyword metadata so plain ID queries find matching Items even when their bodies omit the ID. Do not rely on a coincidental dense match. Include metadata/version in generation fingerprint; incompatible existing indexes require a complete rebuild, preserving the prior active generation until validation succeeds.
3. Apply validated filter predicates before candidate limits in both channels (for example SQLite-derived permitted Item IDs passed as constrained Qdrant filters and lexical SQL predicates). Keep mandatory project/generation pair filtering and final manifest/active revision checks. Reject invalid or oversized filters explicitly, with bounded query size; never fall back to broad search.
4. Write and run failing SRS-linked tests first: opaque source ID absent from title/body, same ID across projects, exact UID, negative ACL, selected scope and stored field equality filters, both-channel prefilters before limit, Item-unique top_k and generation/replay compatibility. Then implement the minimum correction, regression and independent QA (up to three fix/retest rounds).
5. Synchronize executed m4-openapi.json, draft OpenAPI, negative API tests, generated TypeScript client, CLI and traceability. Re-run current full regression, actual synthetic local Qdrant, packaging/container smoke and audits as applicable. Retain real-model/ALM/remote-CI NOT VERIFIED limitations. Request M4 completion approval separately; no M5.

No SRS waiver, ACL widening, live ALM/model access, remote Push/Notion or production deployment is requested. The explicit user decision resolving OI-029 remains valid: list=project_read; retry/resume=project_manage.

Approval requested: authorize this bounded OI-049 corrective implementation and continuation of M4 verification. Until approved, implementation remains stopped under AGENTS.md.
