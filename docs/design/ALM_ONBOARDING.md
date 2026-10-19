# ALM별 프로젝트 등록·수집 범위 선택 설계 (v0.2 Draft)

## 1. 결정
하나의 고정 입력 Form에 모든 ID를 입력시키지 않는다. **ALM 유형 → 서버 연결 → API 검증 → 프로젝트 탐색/선택 → Tracker 또는 Work Item Type 탐색/선택 → 필드 임베딩 정책 → Preflight → 동기화 Job** 순서의 단계형 Wizard를 사용한다. Server Profile은 여러 Project에서 재사용한다. 사용자가 직접 UID를 만들지 않는다.

## 2. 필드/자원 비교
| 구분 | 공통 | Codebeamer | Polarion |
|---|---|---|---|
| 서버 등록 | 표시명, source_type, 서버 기본 URL, TLS 정책, 인증 방식/secret_ref, read-only 검증, API 버전 | 보통 `/v3` 계열 API 프로필, 서버 버전별 기능 차이 | `/polarion/rest/v1` 계열 API 프로필, REST 활성 여부 및 버전 |
| 프로젝트 | 자동 프로젝트 목록, source_project_id, 이름, canonical project_uid | API 응답의 Project ID(숫자형 표기 가능) | Project ID(문자열) |
| 수집 Scope | 전체/선택, 저장된 ID 목록, Field embed policy | `tracker_ids[]` (= 프로젝트 소속 실제 Tracker 인스턴스 ID) | `work_item_type_ids[]` (= 해당 프로젝트 Type enumeration option ID) |
| 사용자 입력 | 서버명/URL, 자격증명 연결, Project/Scope 선택 | Tracker 선택 다중체크 | Type 선택 다중체크 |
| Advanced fallback | API 조회 불가 시 수동 입력 허용하되 preflight PASS 전 Sync 금지 | 수동 Tracker ID + 실제 조회 검증 | 수동 Type ID + enumeration/실제 query 검증 |

**구분 주의:** CB Tracker Type(`Issue`, `Bug` 등)과 Tracker ID는 다르다. Polarion의 Work Item Type은 Codebeamer Tracker와 동일한 독립 컨테이너가 아니다. Codebeamer는 `GET /v3/projects/{projectId}/trackers`; Polarion은 `GET /projects/{projectId}/enumerations/~/workitem-type/~`와 Work Item API를 조합하는 방법을 버전별 검증한다. 필드 Meta 목록은 API 스키마에서 가져온다.

## 3. 단계·UX 정책
1. **종류 선택**: `codebeamer` 또는 `polarion`. 다른 종류 전용 입력을 감추고 소스 종류 변경 시 기존 scope는 자동 승계하지 않는다.
2. **Server Profile**: base_url 유효성 검증, 허용 프로토콜/host allowlist, secret 설정(암호화 저장), connect probe, API 버전 프로필 자동 탐지/수동 선택.
3. **Project Discovery**: 접근 가능한 프로젝트 목록·이름·원본 ID 표시, 사용자 선택 후 DB에 unique `(instance_uid, source_project_id)` 기록. 잘못된 자격증명은 명확하게 오류 표시.
4. **Scope Discovery**: Codebeamer는 Tracker ID 목록, Polarion은 Work Item Type 옵션 목록. 전체 또는 다중 선택, 이름은 UI 표기용만 사용. 숨김·삭제/권한 없는 리소스 구분.
5. **Embedded fields**: Title+Description 기본, 제품별 읽을 수 있는 Field 목록 제시, 선택 변경 시 필요 Chunk만 재임베딩 또는 index generation 필요성 평가.
6. **Preflight**: 서버 연결 상태, Project ID/Scope 유효성, `readable_fields`, API 제한, 모델/DB 상태 및 예상 Item 수 확인. 오류/미지원 기능은 근거와 함께 BLOCKED / DEGRADED.
7. **Submit**: Job 생성, 설정 revision과 scope snapshot 고정. 프로젝트 선택의 변경으로 Item이 실제 삭제되었다고 오판하지 않도록 deleted_state와 out_of_scope 상태 분리.

## 4. JSON Schema 예시 (제품별 discriminated union)
```json
{
  "instance_uid": "server-snowflake-uuid",
  "source_type": "codebeamer",
  "base_url": "https://codebeamer.example.invalid",
  "api_profile": "cb-rest-v3",
  "auth_ref": "vault:alm-cb-01",
  "http_policy": {"rps": 2.0, "burst": 2, "max_inflight": 2, "min_interval_ms": 200, "timeout_seconds": 30},
  "project": {
    "source_project_id": "42",
    "selection_mode": "SELECTED",
    "scope_kind": "TRACKER",
    "source_scope_ids": ["4305", "4306"]
  }
}
```
Polarion 예시는 `source_type: polarion`, `api_profile: polarion-rest-v1`, `scope_kind: WORK_ITEM_TYPE`, `source_scope_ids: ["systemrequirement", "softwarerequirement"]`. 실제 목록과 권한은 대상 서버에서 검증한다.

## 5. 실패 정책 및 테스트
- 401 → 인증 실패, 재로그인/토큰 교체. 403 → 해당 사용자의 접근 권한 부족. 404/empty → ID 오류/숨김/삭제/권한 불가를 추가 진단, 빈 목록만으로 삭제 확정 금지.
- API 자동 탐색 실패 시 관리자 수동 입력 가능하지만 검증 없이 추측한 ID를 저장·임베딩 금지.
- CB Tracker Type을 Tracker ID로 오인, Polarion Type의 숫자 Tracker ID 변환, 동일 이름/서버 중복, Scope 변경 후 대량 삭제 오판을 Mock Test로 검증.
- 구현 인터페이스: `AlmConnector.capabilities()`, `probe()`, `list_projects()`, `list_collectable_scopes(project_uid)`, `list_embed_candidate_fields(scope)`, `validate_selection()`.

**참고:** https://support.ptc.com/help/codebeamer/r3.1/ko/codebeamer/developers_guide/swagger/SwaggerV3_TrackerInformation.html ; https://developer.siemens.com/polarion/advanced-concepts.html ; https://developer.siemens.com/polarion/rest-api-spec.html
