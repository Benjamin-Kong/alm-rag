# ALM RAG — v0.3 Baseline Audit / Corrective Review

**검토일:** 2026-10-19  
**산출물:** 문서·스키마·OpenAPI·계획·Agent 설정 교정본, 구현 코드 아님.  
**현재 판정:** `CONDITIONAL REVIEW CANDIDATE — USER APPROVAL REQUIRED`; 기능/통합 테스트/실 ALM 접속은 모두 미실행.

## 검토 기준 및 결과
| 분류 | 분석·수정 결과 | 남은 제약 |
|---|---|---|
| Q01~Q50 정책 | 50개 질문 요약과 SRS 매핑 파일 생성. SRS 연결 누락 질문 0개. | Q별 Policy summary로만 비교, 원래 장문의 설명과 1:1 문장 대조 불가 |
| 기존 REQ-001~252 | Legacy ID별 252행 추적 매핑 생성. 결정기록에서 직접 언급되지 않은 번호 9개 명시: REQ-001, REQ-003, REQ-004, REQ-005, REQ-006, REQ-007, REQ-008, REQ-009, REQ-010. | 번호가 지정된 243개도 원문 부재로 **요약 수준 매핑**임. 원래 각 REQ 문장은 별도 확보 필요 |
| SRS-001~059 | 59개 고유 SRS ID 확인; 각 Item의 Primary Milestone 1개와 공통 게이트 배정, TEST-001~059 예약 | ID 예약은 실행된 테스트의 증거가 아님 |
| SAD/DATA_MODEL | SQLite active-revision / Qdrant generation / staged publication / overfetch / multi-project 검색 가시성 계약 강화 | 정합성은 M4/M6 crash+race+recall 시험 전 미검증 |
| OpenAPI | 불필요한 `not probability: null` 속성 제거, 인증·조회·운영 API 초안 확장, 권한 scope 표기 | 일부 2xx 응답 payload/pagination 등 상세 스키마는 M1/M5 계약 테스트에서 확정 |
| M1~M6 | 신규 SRS-044~059 Primary Owner 반영; M2 CLI/API 선행, M5 React UI 분리; 단계별 TDD/QA/Human Gate 반영 | 계획이므로 앱 실행 불가 |
| Codex Agent 설정 | Main + 6개 역할 확인; 로컬 샌드박스, on-request 승인을 명시; 동시 Agent는 기본 3으로 제한 | 설치된 Codex CLI 실제 버전/role spawn/Worktree 검증 필요 |
| Docker | 설계 Skeleton 보존, 미구현 실행 사실 오인하지 않도록 문서화 | Docker/Native build, boot 및 image pin 불가능(소스 미구현) |

## 핵심 발견 및 수정 내역
### AUD-01 — Legacy REQ 단일 소스 불완전 (Critical documentation traceability)
`DECISIONS.md`에는 사용자가 질문별로 선택한 Policy와 일부 `REQ-xxx` 번호만 존재하고, 원래 각 REQ 상세 텍스트 전체는 포함되지 않는다. **정책 요약이 원문과 완전히 동등함을 단정할 수 없다.** 숫자 252개를 모두 채웠다는 이유로 커버리지를 PASS로 평가하지 않는다. Decision-to-SRS 50개는 매핑했으며, 직접 확인할 수 없는 9개 번호를 보고한다. Q25가 REQ-117을 supersede함.

### AUD-02 — 59개 SRS Milestone owner 누락 (Fixed)
각 SRS에 하나의 Primary Milestone과 선택적 Shared Gate를 배정했다. Primary 수: M1=11, M2=15, M3=10, M4=6, M5=7, M6=10. 신규 SRS-044~059 포함. M2 Collector의 API 기반 등록·Scope Discovery는 M5 UI 없이 수행 가능하도록 의존성을 수정했다.

### AUD-03 — OpenAPI 관리 계층 누락 (Contract inventory fixed; detailed schemas pending)
기존 문서에 없거나 불완전했던 Admin Session/Login, API key 발급·폐기, Project/Item Explorer, Revision/Chunk Explorer, stage별 Pipeline Job, Integrity/Evaluation, Backup/Restore, Export/Import, Audit/Job Events, health endpoints를 API 목록에 추가했다. 요청·응답 타입/표준 오류/권한 시나리오의 미결 상세 부분은 `API_COVERAGE.md`에 명시했다. `x-required-scope`는 **문서 속성**으로 실제 권한 강제 코드를 의미하지 않는다.

### AUD-04 — SQLite/Qdrant의 Item 게시 정합성 (Design made explicit; unverified)
Item staging → 양 검색채널 검증 → SQLite active revision pointer 교체 → stale candidate 재검증/overfetch → 안전한 GC. 다중 프로젝트는 각기 다른 활성 세대를 가질 수 있다. DB Snapshot/CAS 방식과 garbage collection race를 실제 인덱스 구현 전 테스트 명세로 확정해야 한다.

### AUD-05 — Codex Runtime/Pipeline/Build (Updated instructions, pending verification)
Codex CLI config의 `features.multi_agent`, `agents.*.config_file` 및 sandbox/approval 기본값을 보완했다. 동일 파일 동시 수정/Worktree 격리는 Codex Subagent 자체가 자동으로 보장하는 속성이 아니므로 Main Agent가 별도 관리한다. 미구현 Dockerfile은 배포 준비 완료로 평가하지 않는다.

## Baseline Gate — 승인 가능한 부분과 보류할 부분
- **SPECIFICATION PACKAGE:** 50개 결정 요약 매핑, 59개 SRS owner+Test ID 연결, 정적 문법/파일 검증 통과 시 `DOC_STATIC_PASS`.
- **REQUIREMENT CLAUSE COMPLETENESS:** `PARTIAL / NOT VERIFIED` — Legacy 상세 원문 9개는 질문 결정 기록에서 번호를 찾을 수 없고, 나머지 역시 원문을 모두 포함하지 않는다.
- **OPENAPI EXECUTABLE CONTRACTS:** `PARTIAL / NOT VERIFIED` — 경로·권한 목록은 있지만 일부 응답과 인증 흐름은 설계 후보이다.
- **TECHNICAL INTEGRATION:** `NOT VERIFIED` — Codebeamer/Polarion 실제 버전, Ollama/Qdrant, Docker, Native, Codex CLI 없음.
- **M1 IMPLEMENTATION:** `NOT STARTED`; 사용자 Human Approval을 받을 때까지 구현/외부 push 금지.

## 개발 시작 전 조치
1. 사용자에게 **v0.3 문서 기준선의 조건부 승인**을 요청한다. 기존 결정 정책을 임의 변경하지 않는다.
2. 원래 252개의 REQ 본문 전체가 있는 경우 확보하여 `LEGACY_REQ_TRACEABILITY.csv`를 1:1 Requirement Clause 수준으로 보완하고 별도 미확인 제약을 승인받는다.
3. M1은 DB/Auth/Job/Dev Env 및 기초 계약만 만들고, M2 API discovery는 M5 UI에 의존하지 않도록 유지한다.
4. Codebeamer/Polarion 실서버 기능 차이와 모델/키워드 토큰화는 도입 Milestone에서 `NOT VERIFIED`로 기록하고 실측 검증한다.
5. Codebeamer/POLARION 원본문서, 첨부, 인증정보 및 개인정보는 GitHub/Notion에 미러하지 않는다.

## v0.3 Supplement — 59 executable-test scenarios and protocol compatibility
- Added `docs/testing/TEST_CASES.md` with 43 old SRS Given/When/Then test specs; TEST-044~059 remain described in `TEST_PLAN.md`. These are not executed.
- OpenAPI 3.0.3 conditional schema constraints are documented instead of using unsupported JSON Schema `if/then`; nested schema request validation remains application responsibility.
- Expanded admin session/API Key OR-security, project ACL, CSRF and 401/403/409 response expectations. Full payload schemas remain M1/M5 deliverables.


## 2026-10-19 user disposition (superseding review-candidate status for document baseline only)
The user **conditionally approved v0.3** as the documentation baseline, expressly retaining legacy REQ original-text verification as an OPEN ISSUE. This is a recorded decision, not proof of requirements-clause completeness, nor approval to begin M1 code implementation. Local Git/Codex environment preparation is authorized. Refer to `docs/governance/BASELINE_APPROVAL.md`.
