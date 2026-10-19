# Software Requirements Specification — ALM Unified Retrieval (Review Candidate v0.3)

> 상태: 사용자 정책 50건 반영, 사용자 최종 문서 승인 전. 아직 구현·테스트되지 않음.

## 1. 목적 및 범위
Codebeamer Tracker Item과 Polarion Work Item을 공통 스키마로 수집하고 SQLite에 원본/Revision/첨부를 보존한다. HTML 구조를 분석하여 Field-aware Chunk를 생성하고 Ollama EmbeddingGemma 2와 Qdrant/Keyword Index를 활용해 프로젝트 제한 Hybrid Retrieval REST API를 제공한다.

### 범위 밖 (확정)
- Polarion LiveDoc 일반 텍스트, 독립 문서 컨텐츠 수집
- 첨부파일 내용 파싱/임베딩 및 일반 외부 URL 수집
- 본문 하이퍼링크를 ALM Item UID로 자동 해석
- 관계 1/N-Hop으로 추가 Item 컨텐츠 자동 반환
- ALM의 원격 Item 작성·수정·삭제
- QA에서 Chunk 직접 수정, 승인 전 배포 또는 GitHub Push
- 영구 인덱스 히스토리 및 이전 인덱스 삭제 후 즉시 롤백

## 2. 사용자 검증 가능한 시스템 요구사항
각 `SRS-xxx`는 구현 추적용 고유 ID입니다. 역사적인 `REQ-xxx` 및 질문 Q01~Q50는 `DECISIONS.md`에 보존합니다.

| ID | 분류 | 요구사항 (shall) | 결정 근거 | Milestone |
|---|---|---|---|---|
| SRS-001 | Source Connectivity | 여러 Codebeamer/Polarion 인스턴스 및 인증을 안전하게 등록하고 읽기 전용 조회를 수행한다. | Q01,Q19,Q20 | M1/M2 |
| SRS-002 | Project identity | alm_instance_uid, source_project_id, project_uid를 분리; 동일 이름 및 서로 다른 서버 ID 충돌 없이 식별한다. | Q08 | M1 |
| SRS-003 | Collection scope | 프로젝트별 전체/선택 수집; CB Tracker ID 및 Polarion Work Item Type ID로 지정한다. | Q01,Q09,Q20 | M2 |
| SRS-004 | Items and fields | 모든 선택 Item의 ID/제목/본문/표준 및 커스텀 필드/원본 형식/관계/출처를 보존한다. | Q01,Q03,Q33 | M2 |
| SRS-005 | Raw assets | 첨부파일을 로컬에 내려받아 체크섬·Item UID·원본 URL을 저장하고 현재 임베딩에서 제외한다. | Q02 | M2 |
| SRS-006 | Revision history | 최초 수집 시 최신 Revision 및 이후 관측되는 모든 변경 판을 immutable record로 추가하며 최초 이전 전체 히스토리를 요구하지 않는다. | Q04 | M2 |
| SRS-007 | Delta synchronization | 최초 전체 수집 후 수동 증분 동기화; 변경 시각/Revision/Hash 및 페이지 반복 수집을 활용한다. | Q05 | M2 |
| SRS-008 | Deletion semantics | 삭제가 확인된 Item의 원본/Revision을 남기고 기본 검색 제외; 권한/범위 변화·일시 오류와 구별한다. | Q10 | M2/M4 |
| SRS-009 | Partial field selection | Title+Description 기본 임베딩, ALM/프로젝트/Tracker 또는 Type별 Custom Field 선택; 나머지는 필터·반환용으로 저장한다. | Q03 | M3 |
| SRS-010 | HTML-first | 원본 Wiki/HTML 보존, CB는 서버 Wiki renderer 우선, Polarion 원본 리치텍스트 보존; 실제 표시 HTML과 구분한다. | Q14 | M2/M3 |
| SRS-011 | Structured tables | HTML DOM에서 본문 순서/문단/목록/표를 추출하고 rowspan/colspan·헤더를 Table JSON으로 보존한다. | Q14 | M3 |
| SRS-012 | Table-aware embedding | 표는 Header-Cell 관계를 명시한 자연어/키값 텍스트로 직렬화하고 본문과 분리 청킹한다. | Q14 | M3 |
| SRS-013 | Field-aware chunks | Description은 의미·길이 기반, Custom Field는 기본 별도 Chunk, 긴 Table은 행 묶음으로 처리한다. | Q06,Q14 | M3 |
| SRS-014 | Chunk identity | 모든 Chunk는 project_uid·item_uid·field_id·chunk_key·content_hash·revision_ref를 가진다. | Q06 | M3/M4 |
| SRS-015 | Selective embeddings | 실제 임베딩 입력의 해시와 모델·청킹 설정을 비교하여 영향받는 Chunk만 재임베딩한다. | Q05,Q06 | M3 |
| SRS-016 | Fallback validation | 표 변환 실패 시 제한된 Fallback, 헤더 관계 불확실하면 게시 보류, 기존 활성 Item 유지한다. | Q32 | M3 |
| SRS-017 | Embedding service | Ollama embeddinggemma-2 사용; 로컬/원격 URL과 인증/TLS를 설정으로 분리한다. | Q18 | M1/M3 |
| SRS-018 | Hybrid search | Dense(Qdrant) + BM25 계열 Keyword → RRF 결합; 정확한 Item ID와 필터 검색 지원한다. | Q07 | M4 |
| SRS-019 | Project scoping | 모든 검색 채널에서 허용된 project_uid 목록으로 선필터링; 미지정 시 전체 조회하지 않는다. | Q08,Q27 | M4 |
| SRS-020 | Item grouping | top_k는 고유 Item 수(기본 10,1~100), 결과 Chunk는 item_uid 그룹화 후 전체 Item 복원한다. | Q06,Q12 | M4 |
| SRS-021 | Variable response | 기본 경량 반환; include_full_item/matched_chunks/chunk_text/relations/attachments/max_chunks_per_item 등으로 제어한다. | Q11 | M4 |
| SRS-022 | Relations scope | ALM 공식 관계와 본문 원시 링크는 보존. 자동 본문링크→UID 매핑, 외부 URL 수집, 1/N-Hop 본문 확장 제외한다. | Q33,Q34 | M2/M4 |
| SRS-023 | Item publication | Item별 신규 판을 준비·검증한 뒤 활성화. 실패하면 이전 Item 검색판 유지; 작업 재개와 부분 재처리 지원한다. | Q22 | M1/M4 |
| SRS-024 | Index generations | 모델·청킹 변경 시 새 세대 구축·검증 후 전환; 전환 성공 후 이전 세대 제거. 삭제 후 롤백 비지원한다. | Q24,Q25 | M4 |
| SRS-025 | Independent stages | collect/process/embed/index 각 실행과 sync 통합 실행을 CLI/API/UI에서 지원한다. | Q23 | M1/M5 |
| SRS-026 | Job queue | 프로젝트간 FIFO 순차, 단계별 제한 병렬 및 요청속도 제한; 영속 상태/체크포인트 관리한다. | Q21,Q26 | M1/M5 |
| SRS-027 | Authentication | Web 관리자 로그인, API Key 해시·폐기·Project Scope/읽기·관리 권한; 백엔드 접근검증을 강제한다. | Q19,Q27 | M1 |
| SRS-028 | Secrets and audit | Secrets 암호화/OS keychain, 비밀키와 데이터키 분리, 인증정보/원문 Query 로그 비노출, 감사로그 운영한다. | Q19,Q36 | M1/M5 |
| SRS-029 | Admin UI | 서버 탐색, 프로젝트/Tracker 선택, 수집·Job 상태, HTML/Table/Chunk Explorer, 오류·로그·검색평가 제공한다. | Q15,Q20,Q31,Q36 | M5 |
| SRS-030 | Backup restore | 로컬 자동/수동 백업·보관·복구; SQLite와 Qdrant 버전 정합성 검증 및 재구축 경로 확보한다. | Q28 | M5 |
| SRS-031 | Export import | 프로젝트별 원본/정규화 Item/Revision/첨부 포함한 버전 패키지 Export/Import; 임베딩은 대상 환경에서 재생성한다. | Q29 | M5 |
| SRS-032 | Import merge | Item UID+Revision+Hash 기반 병합, 충돌은 격리, Import 누락 Item 자동 삭제 금지한다. | Q30 | M5 |
| SRS-033 | Integrity assurance | ALM 목록, 필드, 첨부, 변환, Chunk, SQLite/Qdrant 일치/상태를 검증 보고하고 실패 Item 재처리한다. | Q35 | M6 |
| SRS-034 | Retrieval evaluation | 골든셋 Query→관련 Item ID로 Precision@K, Recall@K, MRR 및 Dense/Keyword/Hybrid 비교한다. | Q13 | M6 |
| SRS-035 | Scale target | 10만 Item 계획치로 기능·용량·성능 검증, 평균 Chunk 수는 측정값으로 보정한다. | Q37 | M6 |
| SRS-036 | Search latency | warm Ollama/단일 요청/top_k=10/단일 프로젝트/경량 응답에서 P95≤3초 목표를 실측한다. | Q38 | M6 |
| SRS-037 | Embedding benchmark | CPU·GPU·원격 환경별 chunks/s, tokens/s, batch/변경률 지표를 수집한다. | Q39 | M6 |
| SRS-038 | Execution portability | Windows/macOS/Linux, Docker Compose/Native 실행, 로컬/원격 Ollama·Qdrant를 지원한다. | Q16,Q17,Q18 | M1/M6 |
| SRS-039 | Testing | Unit/Integration/Mock E2E와 requirement→test traceability; PASS/FAIL/NOT VERIFIED 상태를 유지한다. | Q40,Q46 | M1~M6 |
| SRS-040 | Delivery architecture | FastAPI+React TS+독립 Worker의 Modular Monolith, Python CLI와 관리·검색 REST API 구축한다. | Q15,Q41 | M1 |
| SRS-041 | Milestone governance | M1..M6, Main+6 Subagent, Worktree 독립 수정, QA Gate, 최대 3회 재작업, Human Gate 강제한다. | Q42~Q47 | M1~M6 |
| SRS-042 | Docs and repositories | SRS/SAD/SDD/ADR/API/테스트/추적성 문서를 Git 기준; Private GitHub·Notion 미러·승인 이력 관리한다. | Q45,Q48,Q49 | M1~M6 |
| SRS-043 | Approval-before-build | 최종 패키지 검토 승인 전 M1 앱 개발이나 GitHub Push를 시작하지 않는다. | Q50 | 준비 단계 |

## 2.1. Q50 후 사용자 추가 요청: 구현 상세 요구사항 SRS-044~SRS-059
아래 항목은 사용자가 직접 제시한 추가 사항에 대한 설계 구체화이며 Q01~Q50의 선택을 변경하지 않는다. 검토·승인 전 Draft.

| ID | 분류 | 요구사항 (shall) | Milestone |
|---|---|---|---|
| SRS-044 | ALM-aware wizard | 신규 등록 시 ALM 종류(Codebeamer/Polarion)를 먼저 선택하고 제품별 Connection Profile/UI 필드를 제공한다. | M1/M5 |
| SRS-045 | Server discovery | Server URL·인증을 검증한 후 ALM API에서 접근 가능한 Project를 조회하고 ID를 불변 원본값으로 보존한다. 수동 입력은 관리자 고급모드로만 허용한다. | M2/M5 |
| SRS-046 | Product-specific scope | Codebeamer에서는 Tracker ID, Polarion에서는 프로젝트 Work Item Type ID를 조회/선택하고 전체 또는 선택 수집 정책을 저장·검증한다. | M2/M5 |
| SRS-047 | Collection preflight | 수집 전 server/profile/project/scope/선택 필드/속도 설정 및 예상 요청량을 검증하고 Preview 제공; 실패 시 동기화를 시작하지 않는다. | M2/M5 |
| SRS-048 | Token-bounded chunks | 사용자 지정 target/max/overlap/context-budget 설정과 선택 모델의 실제 입력 제한을 검증한다. 본문·표·Field 의미 경계를 우선하며 한 Chunk가 제한을 초과해 조용히 잘리는 것을 금지한다. | M3 |
| SRS-049 | Full item retention | 임베딩 Chunk 크기와 무관하게 Item의 원본 필드·원본 HTML·Table JSON·Revision을 SQLite에 완전하게 보존하고 Item 단위로 복원한다. | M2/M3/M4 |
| SRS-050 | Table atomic semantics | 표 Header-Cell 관계를 유지하면서 행 묶음 분할; 초과 길이 행은 셀/절로 안전 분해하거나 실패로 격리한다. | M3 |
| SRS-051 | Container build | API·Worker·Frontend Dockerfile 및 Compose 토폴로지와 패키지/OS 라이브러리 목록, healthcheck, non-root, 볼륨 및 외부 Ollama/Qdrant 설정을 제공한다. | M1 |
| SRS-052 | Reproducible install | 모든 런타임 종속성을 명시하고 잠금 파일을 생성해 Docker/Native 의존성을 재현 가능하게 설치·CI 검증한다. | M1/M6 |
| SRS-053 | Adaptive throttling | ALM 서버별 request rate, burst, concurrency, 최소 간격, HTTP timeout을 설정하고 API/첨부/렌더링 호출에 공통 적용한다. | M2/M5 |
| SRS-054 | Backoff semantics | 429 또는 지원되는 일시 오류에서 Retry-After 우선, 지수 backoff+jitter 및 최대 대기/시도 횟수·전체 예산을 적용한다. 401/403과 영구 오류는 무분별하게 재시도하지 않는다. | M2 |
| SRS-055 | Failed item isolation | 개별 Item 처리 실패를 단계·원인·수집 판별값과 함께 별도 기록하고 실패 Item을 건너뛰어 나머지 Item을 진행한다. 단, 전역 인증/안전/인덱스 정합성 장애는 중단한다. | M1/M2/M3/M4 |
| SRS-056 | Item replay | 실패 Item을 Item UID+Stage 단위로 조회, 수동 재시도, 체크포인트 기반 재개, 멱등 재처리하고 성공 시 오류를 해제한다. | M1/M5 |
| SRS-057 | Diagnostics | 구조화 로그에 서버/프로젝트/Job/Item/Stage/attempt/HTTP status/error code 및 correlation ID를 보존하고 정지 원인·실패 집계를 UI/API에 노출한다. Secret·원본문장 로그는 기본 금지한다. | M1/M5 |
| SRS-058 | TDD requirement | 신규 로직은 실패하는 Unit/Contract Test부터 작성(Red) → 최소 구현(Green) → Refactor → 회귀 테스트로 진행하며 증거를 PR/보고서에 첨부한다. | M1~M6 |
| SRS-059 | Gate tests | 제품별 UI/스키마, Chunk 길이 및 표 분할, 컨테이너 이미지 Build/Boot, 429 pacing, Fail-safe/retry, TDD 증거 검사를 CI/QA Gate에 추가한다. | M1~M6 |

## 3. 주요 Given/When/Then 인수 기준

### AC-01: 프로젝트 범위 제한 (SRS-002/019)
**Given** Codebeamer A와 Polarion B가 동일 DB에 있고 API Key가 프로젝트 A만 조회할 수 있을 때, **When** B 또는 무지정 전체 검색을 요청하면, **Then** 서버가 접근을 거부하거나 명시적 프로젝트 지정을 요구하고 다른 프로젝트의 텍스트·점수·ID를 누출하지 않아야 한다.

### AC-02: 커스텀 필드만 수정 (SRS-009/015)
**Given** Title/Description 미변경, 비임베딩 Status만 수정되었을 때, **When** 증분 동기화하면, **Then** SQLite 필드 이력을 갱신하고 Qdrant Payload만 갱신하며 임베딩 호출 수는 0이어야 한다. 임베딩 대상으로 설정된 Verification Method만 바뀌면 해당 필드 Chunk만 재임베딩한다.

### AC-03: 동일 Item 다중 Chunk (SRS-013/014/020)
**Given** Item 1001의 본문, 표, 커스텀 필드가 별도 Chunk로 인덱싱될 때, **When** 관련 Query의 top_k=10으로 검색하면, **Then** item_uid 1001은 결과에서 최대 한 번 등장하고 각 매칭 Chunk 출처를 선택적으로 반환해야 한다.

### AC-04: 복잡한 병합 표 (SRS-010~012/016)
**Given** rowspan/colspan이 포함된 HTML 표가 있을 때, **When** DOM→Table JSON→의미 직렬화를 수행하면, **Then** 원본 좌표·헤더/셀 관계가 유실되거나 왜곡되지 않아야 한다. 보존 여부가 판정 불가하면 기존 검색판을 유지하고 실패 상태를 노출한다.

### AC-05: 작업 장애 (SRS-023/026)
**Given** 기존 Item Rev3가 검색 중일 때, **When** Rev4 일부 Chunk 임베딩에서 실패하면, **Then** Rev3 검색 결과만 나타나고 재시도 시 ALM 원본 재다운로드 없이 남은 처리부터 이어야 한다.

### AC-06: 삭제 검출 (SRS-008)
**Given** 수집 목록에서 Item이 사라졌을 때, **When** 권한 오류·프로젝트 선택 변경을 배제하고 삭제를 확인하면, **Then** 검색에서 제외하고 SQLite의 이력과 첨부파일은 유지해야 한다.

### AC-07: Retrieval 응답 (SRS-018~021)
**Given** project_uids 지정 및 유효한 키, **When** 한글/영문 Query로 검색하고 include_full_item=false이면, **Then** 기본 필드와 매칭 Chunk를 반환하고 전체 필드는 생략한다. include_full_item=true이면 원문과 모든 사용자 정의 필드를 포함한다.

### AC-08: Git/Notion/Human Gate (SRS-041~043)
**Given** QA Gate PASS 이지만 사용자가 Milestone 완료를 아직 승인하지 않았을 때, **When** Main Agent가 다음 Milestone 진입을 시도하면, **Then** 실행을 멈추고 승인 요청 보고서를 제시해야 한다. Github Push 및 Notion 업로드는 승인 정책과 기밀 분류를 준수해야 한다.

### AC-09: 제품별 등록 위저드 (SRS-044~047)
**Given** ALM 종류를 Codebeamer로 지정하면, **When** 연결 검증 및 프로젝트 탐색에 성공하면, **Then** 프로젝트 ID와 Tracker ID 목록이 나타나고 선택한 Tracker만 수집한다. Polarion 선택 시 Tracker 필드는 나타나지 않고 Work Item Type 선택 UI와 필터가 작동해야 한다. 수동 ID는 검색 실패 시 경고 및 검증을 거친다.

### AC-10: 과도하게 긴 Item (SRS-048~050)
**Given** Description 15,000 tokens 및 행 100개가 있는 표가 존재할 때, **When** Chunk를 생성하면, **Then** 한 Chunk도 검증된 모델 입력 한도를 초과하거나 조용히 잘리지 않고, 모든 원본문자는 SQLite에 남으며 활성 Item 상세 조회로 전부 복원되어야 한다.

### AC-11: 429 Throttling 및 Retry (SRS-053~054)
**Given** 2 RPS 제한과 429 Retry-After: 15 응답을 가진 Mock ALM일 때, **When** 페이지/상세/첨부/렌더링 요청을 수행하면, **Then** 서버별 누적 호출 속도를 준수하며 15초 이상 대기한 뒤 제한된 횟수로 재시도한다. 401/403은 인증·권한 오류로 분류한다.

### AC-12: Item 단위 Fail-safe (SRS-055~057)
**Given** 100개의 Item 중 3개에 Parser/Embedding 오류가 있을 때, **When** Sync를 실행하면, **Then** 나머지 97개를 정상 처리하고 3개를 `FAILED_ITEM` 단계별 오류 목록에 기록한다. 사용자 요청으로 각 Item만 재실행할 수 있으며 기존 활성 검색 판은 유지한다. 전역 인증 만료 시 안전하게 PAUSED/BLOCKED 상태로 전환한다.

### AC-13: Docker 및 TDD Gate (SRS-051~052/058~059)
**Given** M1 이미지와 개발 로직을 작성하면, **When** CI를 실행할 때, **Then** Docker Build·API/Worker start·환경설정·볼륨을 검증하고 변경 기능에 대한 Red/Green 증거, Unit/Integration/Mock E2E를 연결해야 한다. 이미 통과한 테스트를 단순 실행한 기록은 TDD 증거로 간주하지 않는다.

## 4. 비기능 요건
- 보안: 서버 측 Project ACL 검사, Secret at rest 보호, 인증·인증실패 감사, ALM API는 읽기 전용.
- 성능: 100,000 Item 데이터; Warm 단일 검색에서 경량 top_k=10, P95 3초 이내 **목표**. 하드웨어 미정이므로 검증 전 보장하지 않는다.
- 운영: 프로젝트별 동기화는 FIFO로 직렬화, 내부 API/Parser/Embedding 제한 병렬.
- 복구: SQLite 원본·Revision은 신뢰 저장소; 검색 인덱스는 재구축 가능.
- 배포: Windows/macOS/Linux 및 Docker/Native.

## 5. 종료 기준
해당 Milestone의 적용 SRS 항목이 모두 설계·코드·테스트 산출물에 연결되고, 적용 가능한 필수 자동 테스트 PASS, Critical/Major 미해결 0건, 미검증 항목과 예외가 보고되며 사용자 서면 승인이 있어야 완료한다.

## 6. 미확정·기술 검증 항목
`docs/review/OPEN_ISSUES.md`의 OI-001~ 항목은 사용자가 정책을 다시 선택해야 한다는 의미가 아니라 구현 전 샘플/환경/기술 검증이 필요한 항목입니다.


## 4. Baseline 검토 제한 및 검증 기준 (v0.3)
- 이 문서는 **59개 통합 SRS**의 구현 요구사항을 기록한다. `DECISIONS.md`의 50개 결정 요약은 모두 `DECISION_COVERAGE.csv`로 매핑된다.
- 252개 과거 REQ 문장을 한 줄씩 완전히 대조했다는 증거는 없다. 일부 원래 REQ 원문은 제공된 패키지에 없으므로 `LEGACY_REQ_TRACEABILITY.csv`에서 불확실성을 표시한다. Q25가 수정한 REQ-117을 재활성화하지 말 것.
- `TRACEABILITY.csv`는 각 통합 SRS의 **Primary Milestone** / Shared Gates / Test ID를 정의한다. Test ID는 이름만 예약되어 있고 실행 테스트는 미구현이다.
- ALM 서버 등록·프로젝트/Scope API(M2)와 React 위저드(M5)는 서로 다른 배포 단계이다. M2는 UI 없이 REST/CLI로 수집 검증 가능해야 한다.
- 액세스 제어는 검색뿐 아니라 UID 기반 Item·Job·첨부·백업·로그 API도 서버에서 검증해야 한다. 임베딩 서버/DB/Notion/GitHub로 ALM 실데이터를 무단 전송할 수 없다.
- 실패 Item 발생 시 변경 신규판 게시를 막고 이전 활성판을 유지한다. 실제 삭제인지 Scope 변경인지 검증 전 검색 판을 삭제하지 않는다.
- 시퀀스·API Contract의 구체화는 `SAD.md`, `DATA_MODEL.md`, `INTERFACES.md`, `API_COVERAGE.md`에 기록. 구현 전 사용자 승인 필요.
