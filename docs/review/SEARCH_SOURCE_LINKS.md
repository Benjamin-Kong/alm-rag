# 검색 결과 ALM ID·원문 링크 — 2026-10-26

## 승인 및 동작

사용자는 검색 결과의 해당 청크에 ALM ID와 링크 표시 가능 여부를 확인한 후 “진행해”로 구현을 승인했다. SRS-014/020의 청크 소속 Item 및 Item 단위 그룹화를 유지하고 SRS-024의 권한 검사를 그대로 적용한다.

- 검색 결과와 펼친 일치 청크에 `ALM ID`와 `ALM 원문 열기`를 표시한다. 청크는 소속 Item의 링크를 공유한다.
- 검색 API `SearchHit`에 `source_item_id`(필수 문자열), `source_url`(nullable 문자열)을 추가한다. 전체 원본 포함 옵션과 무관하게 제공한다. OpenAPI JSON/YAML과 생성 TypeScript 타입을 동기화했다.
- 원본 ID는 SQLite `items.source_item_id`에서 가져온다. 링크는 현재 등록된 서버 기본 URL과 프로젝트/Item ID로 생성하므로 기존 데이터 재수집·재색인은 필요 없다.
- Codebeamer `…/cb/api` → `…/cb/issue/{id}`, Polarion `…/polarion/rest/v1` → `…/polarion/redirect/project/{project}/workitem?id={id}`. 프록시 context path를 유지하고 ID를 인코딩한다.
- 저장된 원본의 portal/source URL은 동일 origin·해당 Item의 허용된 브라우저 경로일 때 보존한다. REST self URL은 브라우저 링크로 사용하지 않는다. 기준 URL이 유효하지 않으면 null과 `원문 링크 없음`을 표시한다.
- HTTP(S)만 허용하며 자격증명 포함 URL·외부 origin·예기치 않은 query를 사용하지 않는다. 링크는 `noopener noreferrer`로 새 탭에서 열고, 클릭 전 추가 ALM 요청을 보내지 않는다.
- 링크는 현재 원본 Item을 연다. 검색에서 사용한 과거 revision이나 특정 청크 위치로 이동한다는 보장은 없다.

URL 형식 근거: [PTC Codebeamer](https://support.ptc.com/help/codebeamer/plus/r3.2/en/codebeamer/cb_dpt_change_mgmt_domain.html), [Siemens Polarion](https://developer.siemens.com/polarion/2512/basic-concepts.html).

## TDD 및 검증

PASS/FAIL은 실제 실행 결과이며 아래 전체 백엔드 결과와 최종 추가 테스트 결과는 서로 다른 실행이다.

| 단계 | 명령/범위 | 결과 |
|---|---|---|
| Red | `pytest tests/test_retrieval.py -k alm_identity` | 2 FAIL: `source_item_id` KeyError |
| Red | `pytest tests/test_source_links.py …` | 수집 오류: 신규 helper 모듈 미구현 |
| Red | Vitest explorer `chunks display` | 3 FAIL: ALM ID 미표시 |
| Green | 최초 source_links + retrieval | 18 PASS |
| 회귀 | `.venv/bin/pytest -q` (최종 테스트 보강 전) | 564 PASS, 6 SKIP, 75.89초 |
| 최종 보강 | retrieval + m4_filters + source_links + m4_api | 53 PASS, 7.41초 |
| UI | `npm --prefix frontend test` | 31 PASS |
| 빌드 | `npm --prefix frontend run build` | PASS |
| 브라우저 | `npm --prefix frontend run test:e2e` | 11 PASS; 결과/청크 ID와 링크·새 탭 속성 검증 포함 |
| 독립 QA | QA agent, 소스 읽기 전용 검토와 최종 source_links/retrieval/m4_filters 실행 | 44 PASS, 차단 Critical/Major 없음 |
| 정적 | `validate_baseline.py`, `git diff --check`, 프로젝트 TOML parse | PASS; 정적 검증은 앱 테스트 증거와 별도 |

QA 보강 중 Polarion 4개 테스트는 공용 Codebeamer fixture의 TRACKER 삽입 때문에 검색 전 FAIL했다. Item fixture 생성 후 source/selection을 전환하도록 테스트 설정을 수정한 뒤 53개 및 독립 44개가 PASS했다. 제품 코드 오류로 분류하지 않았다.

실행 환경: `.venv/bin/python`, Node 22 PATH. 기본 Node 25는 simdjson dylib 누락으로 실행되지 않아 기존 Node 22를 사용했다. Codex CLI 0.163.0 확인. E2E 첫 실행은 sandbox 로컬 포트 EPERM으로 시작하지 못했고, 승인된 재실행에서 11개 통과했다.

## NOT VERIFIED / 잔여 제약

- 실제 Codebeamer/Polarion에서 링크 클릭 성공 및 별도 프록시 재작성 환경 호환성은 검증하지 않았다. 원본 ALM 로그인과 권한은 해당 서버가 적용한다.
- 전체 회귀의 환경 의존 6 SKIP은 PASS로 계산하지 않는다.
- 외부 Push/배포/실 ALM 접근은 이 변경에서 수행하지 않았다.

## 2026-10-27 원격 pull·병합 검증

사용자의 `git pull` 및 충돌 병합 요청에 따라 `codex/m6-quality`를 `3d423b5`에서 `e3ddd86`으로 fast-forward했다. 원격 커밋 `2f196f0`(선택 Scope 필드 조회), `e3ddd86`(서버 프로필 관리·사전 검증 개선)을 반영하고 기존 검색 ID·링크 변경을 복원했다.

- 유일한 텍스트 충돌은 `OPEN_ISSUES.md`의 중복 OI-067이었다. 원격 OI-067을 유지하고 검색 결과 변경을 OI-068로 재번호화하여 두 기록을 보존했다. 미해결 Git 충돌과 충돌 마커는 없다.
- OpenAPI와 TypeScript 재생성 결과가 자동 병합된 파일과 일치했다. 원격 API와 검색 응답 필드를 모두 보존했다.
- 전체 Python **583 PASS / 6 SKIP** (78.02초), UI **32 PASS**, 빌드 **PASS**, 최종 Chromium E2E **11 PASS** (9.3초), 문서 정적 검증 및 diff whitespace 검사 **PASS**.
- E2E 최초 실행은 **9 PASS / 2 FAIL**이었다. 두 마법사 테스트가 원격에서 추가된 필드 조회 버튼을 누르지 않아 Custom 필드 선택에서 timeout이 발생했다. 테스트에 명시적 버튼 클릭을 추가하고, 클릭 전 fields 요청 없음 및 클릭 후 `scope_ids=t` 단일 요청을 검증하도록 보강한 뒤 11개가 통과했다. 제품 로직은 변경하지 않았다.
- 독립 QA의 병합 검토 및 관련 Python **95 PASS**. 원격 기능과 검색 기능 공존을 확인했다.
- 변경사항은 로컬 미커밋 상태로 유지했다. 복구용 `stash@{0}`도 보존했다. Push·배포·실 ALM 접속은 수행하지 않았다.
