# Unified ALM Data Model (Draft)

## Logical entities and minimum keys
| Entity | Key | Key attributes |
|---|---|---|
| AlmInstance | instance_uid | source_type, base_url, display_name, auth_ref, API compatibility profile |
| Project | project_uid | instance_uid, source_project_id, name, url, selection_policy |
| Container | container_uid | project_uid, source_kind(tracker/workitem_type), source_container_id, name |
| Item | item_uid | project_uid, source_item_id, type, status, deleted_state, active_revision_uid |
| ItemRevision | revision_uid | item_uid, source_revision, captured_at, modified_at, raw_payload, hash |
| FieldDefinition | field_def_uid | instance_uid, scope, source_field_id, kind, data_type, embed_policy |
| FieldValue | revision_uid+field_def_uid | raw_value, normalized_value, source_format |
| ContentBlock | revision_uid+block_uid | field_def_uid, block_order, type(text/table), raw_html, table_json, normalized_text |
| Attachment | attachment_uid | item_uid, revision_uid, source_url, filename, checksum, disk_path, download_status |
| Relation | relation_uid | revision_uid, original_relation_type, source_target_id, target_uid(optional) |
| Chunk | chunk_uid | revision_uid, field_def_uid, block_uid, chunk_key, input_text, content_hash, model_fingerprint |
| IndexGeneration | generation_uid | project_uid, model/config, state, validation evidence, activated_at |
| IndexPoint | point_uuid | generation_uid, chunk_uid, vector_status, source_hash |
| Job/Step | job_uid/step_uid | project_uid, type, state, retry_count, checkpoint, errors |
| ApiPrincipal | key_uid | key_hash, project_scopes, role, revoked_at |
| AuditEntry | audit_uid | actor, action, target, occurred_at, outcome |

**Polarion Container**: Work Item Type classification only; do not pretend it is a Codebeamer Tracker or require LiveDoc extraction.

## Portable Unified Item JSON
```json
{
  "schema_version": "1.0-draft",
  "instance_uid": "cb-prod",
  "project_uid": "cb-prod:project-42",
  "container_uid": "cb-prod:tracker-300",
  "item_uid": "cb-prod:project-42:item-1001",
  "source": {"kind": "codebeamer", "project_id": "42", "item_id": "1001", "url": "https://cb.example.invalid/item/1001"},
  "revision": {"revision_uid": "rev-example-5", "source_revision": "5", "captured_at": "2026-10-19T00:00:00Z"},
  "title": "Ethernet Communication",
  "description": {"source_format": "wiki", "raw_text": "...", "html": "<p>...</p><table>...</table>"},
  "fields": [{"source_field_id": "1006", "name": "Safety Level", "source_type": "choice", "raw_value": "QM", "normalized_value": "QM", "embedding_enabled": false}],
  "content_blocks": [{"id": "description:table:0", "type": "table", "order": 2, "table_json": {"headers": ["Signal", "Action"], "rows": [["IGN OFF", "Stop SOME/IP"]]}}],
  "relations": [{"source_kind": "tracked", "target_source_id": "999", "target_item_uid": null}],
  "attachments": [{"filename": "diagram.png", "sha256": "example-not-actual-hash"}],
  "deleted_state": "active"
}
```

## Structured table JSON (target)
`cells[]` must preserve original row/column coordinate, rowspan, colspan, header association, cell HTML fragment and flattened text; `headers`/`rows` are convenience projections only. Multi-row headers must not be flattened incorrectly. Document-order IDs are stable only to extent DOM permits; hash controls delta.

## Invariants
- Unique `(instance_uid, source_project_id)` and `(project_uid, source_item_id)`; source revision key is qualified by item_uid.
- Missing/unauthorized/deleted are independent states and never silently converted.
- Relation target may be absent locally because of scope/permissions; not necessarily an error.
- No unverified cross-instance name matching.
- Search result item body is restored from the **active Revision** in SQLite; not from Qdrant payload.

## v0.2 확장 엔티티·속성
- **ServerProfile/AlmInstance**: `source_type` enum, `api_profile`, `base_url`, `auth_ref`, TLS/CA, `supports_discovery`, `capability_probe_at`, `rate_limit_policy_uid`.
- **ProjectSelection**: `project_uid`, `selection_mode`(ALL/SELECTED), `scope_kind`(TRACKER/WORK_ITEM_TYPE), `scope_ids[]` (원본 문자열 유지), `config_revision`, `preflight_status`, `scope_snapshot_hash`.
- **Container**: Codebeamer는 실제 Tracker entity. Polarion은 Work Item Type classification only. Unique identifiers have source-specific namespaces.
- **Chunk**: `input_tokens`, `source_span_offsets`, `row_ids`, `embedding_input_digest`, `tokenizer_id`, `effective_max_input_tokens`, `truncation_detected`(always false).
- **RateLimitPolicy/State**: `(instance_uid, credential_scope)` 기준 RPS/burst/inflight/min_interval/Retry-After pause/circuit state; persistent `next_eligible_at`.
- **FailedItem/JobItemAttempt**: `job_uid`, `project_uid`, `item_uid`, `revision_uid`, `failed_stage`, `error_class`, `retryable`, `attempts`, `trace_id`, `replay_state`.
- **Job**: terminal states include `COMPLETED_WITH_ERRORS`, `PAUSED`, `BLOCKED`, `FAILED`, `CANCELLED`. `progress_total`, `succeeded_items`, `failed_items`, `skipped_items` consistent accounting.
- Migrations and enums are design proposals, not applied; SQLite migration scripts to be created and tested in M1.

## v0.3 무결성·권한 스키마 불변조건
| Entity/Field | Constraint | Why |
|---|---|---|
| `Item.active_revision_uid` | FK -> revision.item_uid match; null permitted before first publish; switch in SQLite transaction | 어떤 후보도 미완성 Revision을 공개하지 않음 |
| `Chunk(revision_uid, chunk_key, fingerprint)` | Unique per version, complete coverage verified | Item 재처리 시 임의 중복 방지 |
| `IndexPoint(generation_uid, chunk_uid)` | stable deterministic point key; status PREPARED / READY / RETIRED | Qdrant stage retry idempotency |
| `Project.active_generation_uid` | FK -> VALIDATED generation of same project | 새 인덱스 전환 성공 후 이전 세대 정리 |
| `ProjectSelection(config_revision, scope_kind, scope_ids)` | CB=TRACKER, Polarion=WORK_ITEM_TYPE, snapshot stable during job | 범위 변경과 Item 삭제 오판 방지 |
| `Job(project_uid, checkpoint, state)` | global FIFO project lock, states queued/running/partial/blocked/cancelled | Q26 단일 프로젝트 작업 |
| `RateLimitState` | instance+credential_scope, next_allowed request state persisted | 모든 API 호출에 서버 RPS 정책 유지 |
| `FailedItem` | unique `(job_uid,item_uid,failed_stage,revision_uid)` with last failure and replay counter | Item 별 격리·재실행 추적 |
| `ApiPrincipal` / `PrincipalProjectGrant` | server-enforced project, method scopes; never trust UI field | project leakage 차단 |

`item_uid`/`project_uid`는 기계적 canonical ID이다. 실제 UID 생성 시 필드 구분과 길이 기반 encoding/UUIDv5 또는 collision-resistant digest를 사용해 문자열 이어붙이기 충돌이 없도록 한다. Source field/Scope 정규화에서 원본 ID를 손실 없이 별도 보존한다.

**미결 구현 설계:** SQLite writer policy / indexed staging row schema / GC checkpoint / migration 전략 / 활성 검색 세대 전환 재시도 수학적 상한을 M1 설계·M4 코드 테스트로 확정. 여기서 실제 SQL migration을 실행하지 않음.
