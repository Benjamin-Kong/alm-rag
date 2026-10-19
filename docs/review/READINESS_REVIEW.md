# 개발 착수 전 설계 검토 보고서 — Review Candidate v0.3

**상태: DOCUMENT REVIEW REQUIRED. 구현 승인 전.**

## 검토한 정책
- Q01~Q50의 최신 사용자 선택 50건 모두 `DECISIONS.md`에 반영.
- 최종 변경 우선순위: Q09=C, Q25=A, Q33=A, Q34=A, Q45=C, Q48=B+Notion, Q49=B.
- 기능 요구: 수집/Normalization/Field-aware Chunk/Embedding/Hybrid Retrieval/Job/Web API/권한/백업/E2E.

## 중요한 설계 위험·교정
1. **Polarion HTML:** API의 Rich Text `text/html` 원시 소스와 렌더된 HTML은 동일하다고 가정할 수 없음. Siemens REST 문서에 'get Rich Text field content as processed HTML' 미지원 항목 존재. M2 실제 버전 샘플로 검증해야 함.
2. **Codebeamer:** `POST /v3/projects/{projectId}/wiki2html`는 Wiki를 서버 컨텍스트로 HTML 변환 가능하지만 실제 서버 버전·필드 범위·첨부 링크를 테스트해야 함.
3. **아이템 게시 원자성:** Qdrant 다중 Point+SQLite는 ACID 분산 트랜잭션이 아니므로 '단일 API 원자적 교체'로 주장하면 안 됨. active_revision 검증, staged point 후처리, 실패 시 동일 Revision 복원 검증 필요.
4. **동일 Index 삭제 정책:** Q24에서 설계한 롤백은 Q25가 A로 변경됨. 이전 인덱스 자동 삭제 후 롤백은 불가능; 전환 직전 검증과 DB 재구축으로 복구.
5. **BM25 구현:** Qdrant sparse BM25 또는 SQLite FTS5는 정확히 동일하지 않음. 형태소(한글)/기술 토큰/하이픈/Hex 등 분석기를 테스트하고 M4에서 결정.
6. **Polarion 컨테이너:** Type은 Tracker와 동일한 별도 컨테이너 개체가 아님. 커넥터가 Work Item Type 필터/페이지네이션을 사용하도록 설계.
7. **EmbeddingGemma 2:** Ollama의 실제 반환 차원, 버전·모델 digest, 텍스트 prefix 정책을 실행 환경에서 검사. 인덱스 모델 혼합 금지.
8. **Private GitHub / Notion 외부 반출:** 사내 ALM 데이터는 기본 업로드 제외. Git에는 원본 ALM 덤프/첨부/시크릿 미커밋. Notion에는 비식별 기술 문서/QA 요약만 게시하는 정책.
9. **Mock ≠ 실제 ALM 검증:** 서버 버전/권한/문서 Rich Text/파일다운로드/특수 필드 연동은 NOT VERIFIED로 기록할 것.

## 보류 사항 (구현 전 승인 또는 환경 검증)
- 사용 Codebeamer/Polarion 제품 버전과 인증 제약, 샘플 Item 컨텐츠; 실제 API 접근 가능 여부.
- GitHub Private Repo 주소/Owner 및 Push 범위; Notion 기록 시 기밀/비밀정보 분류 정책.
- Ollama/Qdrant 원격 TLS·API 키 및 운영 PC 자원 사양.
- M4 Keyword Engine(FTS5/Qdrant Sparse) 구체 선택 및 Korean BM25 토크나이저.
- 복잡한 표의 구조 보존 검증법, HTML 콘텐츠 보안 렌더링.
- Project global 10만 Item에서 Chunk 개수·디스크/RAM 추정치 실측.

## 판정
**문서 패키지 초안 생성: PASS (파일 검사 후).**
**실제 환경 호환성 검증: NOT VERIFIED.**
**M1 구현 시작 승인: PENDING USER APPROVAL.**

본 문서의 PASS는 문서 패키지의 자체 정합성 검사에 한정하며 기능 구현/시험 완료를 의미하지 않습니다.

## 2026-10-19 추가 사용자 요청에 대한 상세 검토(v0.2)
| 검토 주제 | v0.1 상태 | v0.2 보완 | 완료 판정 |
|---|---|---|---|
| 제품별 프로젝트 등록 | SRS-001/003/029 일반 형태, 제품별 폼/Type mismatch 불명확 | SRS-044~047 및 ALM_ONBOARDING.md | **SPECIFIED / NOT IMPLEMENTED** |
| Chunk 크기 | SRS-013/015, 길이 상한/모델 토큰 정책 없음 | SRS-048~050 및 CHUNKING_POLICY.md | **SPECIFIED / NOT VERIFIED** |
| Dockerfile | Docker Compose/Native 요구사항은 있으나 실제 파일 부재 | SRS-051~052 및 deploy Skeleton / Dependencies | **SCAFFOLDED / NOT BUILT** |
| REST API Throttling | SRS-026의 제한 병렬, 구체 RPS/429 정책 미흡 | SRS-053~054, API_THROTTLING_AND_RETRY.md | **SPECIFIED / NOT IMPLEMENTED** |
| Fail-safe/Replay | SRS-023/025/026의 Job checkpoint, Item retry UI/API 불명확 | SRS-055~057, FAIL_SAFE_AND_REPLAY.md 및 Draft API | **SPECIFIED / NOT IMPLEMENTED** |
| TDD | Unit/Integration/E2E 의무는 있으나 Test-first 절차 없음 | SRS-058~059 및 TDD_POLICY.md, Agent 규칙 | **SPECIFIED / NOT IMPLEMENTED** |

### 별도 설계 검토 중요 발견
- v0.1의 `SRS-026`이 API 병렬성과 ALM rate-limiting을 묶어 명시했으나 **RPS는 동시성 수와 같지 않다**. 두 정책 분리.
- '하나 Item의 모든 정보가 Chunk 하나에 들어가야 한다'는 요구는 기존 field-aware Chunk 및 item_uid grouping 정책과 상충한다. 완전한 원본 복원(SQLite) + 안전하게 분할된 N Chunks 방식 채택.
- Google/Ollama EmbeddingGemma 2 문서의 text-context 8K와 Ollama Tag meta의 별도 수치는 일치하지 않을 수 있다. 런타임 모델 정보/실제 truncation을 측정해야 한다.
- DB+Qdrant 분산 원자성을 제공하는 것처럼 작성하지 않고 Active Revision 검증과 Worker Kill/Test evidence가 필요.
- ALM 별 Type/Tracker 명칭만 UI에서 바꾸고 저장 항목을 동일하게 처리하지 않도록 `source_type`+`scope_kind` 명시.
- 운영 보안: ALM 인증정보/원본문자와 로그는 외부 Notion/Private GitHub에 직접 업로드하지 않음.

**최종 상태: DOCUMENTS REVIEWED, IMPLEMENTATION NOT STARTED, HUMAN APPROVAL PENDING.**
