# SRS Test Cases — DRAFT, NOT EXECUTED

Test IDs map 1:1 to consolidated SRS. These are specification-level Given/When/Then scenarios, not implemented tests or successful test evidence.

| Test ID | SRS | Given | When | Then | Status |
|---|---|---|---|---|---|
| TEST-001 | SRS-001 | 관리자가 Codebeamer·Polarion 서버를 등록한다 | ALM 종류/인증 프로필을 입력한다 | 유효한 서버/인증으로 읽기 전용 연결을 관리하고 잘못된 접근은 실패 상태가 된다 | NOT VERIFIED |
| TEST-002 | SRS-002 | 서로 다른 ALM 서버에 동일한 Project 명칭·Item ID가 있다 | Project 및 Item을 저장한다 | 프로젝트·아이템 UID 충돌 없이 분리된다 | NOT VERIFIED |
| TEST-003 | SRS-003 | ALL 및 SELECTED 범위의 프로젝트가 존재한다 | Tracker ID 또는 Polarion Work Item Type을 선택한다 | 선택 범위만 수집하며 다른 종류의 Scope ID는 검증 실패한다 | NOT VERIFIED |
| TEST-004 | SRS-004 | 원본 Item에 표준/커스텀 필드와 원시링크/공식 관계가 있다 | Collector가 Item을 읽는다 | 모든 원본 필드·메타데이터가 손실 없이 저장된다 | NOT VERIFIED |
| TEST-005 | SRS-005 | Item에 여러 첨부 파일이 있다 | 수집을 실행한다 | 파일은 체크섬 검증 후 로컬 보존되고 임베딩 입력에서는 제외된다 | NOT VERIFIED |
| TEST-006 | SRS-006 | 기존 Item이 RevA이고 서버가 RevB가 되었다 | 증분 동기화한다 | 관측한 RevA·RevB가 불변 이력으로 남는다 | NOT VERIFIED |
| TEST-007 | SRS-007 | 최초 동기화를 완료했다 | 수동 증분 동기화한다 | 변경된 Item만 처리하고 전체 페이지네이션 누락이 없다 | NOT VERIFIED |
| TEST-008 | SRS-008 | Item이 목록에서 사라졌다 | 접근권한/범위가 변경되거나 삭제가 발생했다 | 권한/범위 누락은 실제 삭제로 오분류하지 않는다 | NOT VERIFIED |
| TEST-009 | SRS-009 | Title·Description·추가 선택 필드가 있다 | 임베딩 필드 설정에 따라 처리한다 | 비선택 필드는 저장하되 임베딩하지 않는다 | NOT VERIFIED |
| TEST-010 | SRS-010 | Codebeamer Wiki와 Polarion Rich HTML을 받는다 | 서버별 정규화를 수행한다 | 원본을 유지하고 렌더링 결과를 구분한다 | NOT VERIFIED |
| TEST-011 | SRS-011 | 병합셀 포함 표가 있다 | HTML DOM을 변환한다 | 셀 좌표·헤더·표 순서가 구조적으로 보존된다 | NOT VERIFIED |
| TEST-012 | SRS-012 | 표의 헤더·행 정보를 구조화했다 | 임베딩 직렬화를 생성한다 | Header-Value 관계가 명시된 텍스트로 생성된다 | NOT VERIFIED |
| TEST-013 | SRS-013 | 긴 Description·표·복수 Custom Field가 있다 | Chunker를 실행한다 | Field 경계를 보존하고 필요한 경우 행/문장 단위로 분리한다 | NOT VERIFIED |
| TEST-014 | SRS-014 | 동일 Item의 다중 Chunk가 생성된다 | 청크를 저장한다 | item_uid/project_uid/revision_uid 및 stable hash가 모두 연결된다 | NOT VERIFIED |
| TEST-015 | SRS-015 | 비임베딩 필드만 변경되었다 | 증분 동기화한다 | 임베딩 API 호출은 0회이며 필요한 Payload만 갱신한다 | NOT VERIFIED |
| TEST-016 | SRS-016 | HTML 표 변환이 구조 보존에 실패한다 | Fallback을 시도한다 | 안전성이 검증되지 않으면 신규 활성 판을 게시하지 않는다 | NOT VERIFIED |
| TEST-017 | SRS-017 | 로컬 또는 원격 Ollama 엔드포인트가 설정됐다 | 임베딩 요청을 보낸다 | 모델 fingerprint/dimension을 검증하고 설정된 TLS·인증을 준수한다 | NOT VERIFIED |
| TEST-018 | SRS-018 | 동일 프로젝트 문서가 키워드와 벡터에 색인됐다 | Hybrid 검색을 수행한다 | 두 채널 점수를 RRF로 결합하고 정확 Item ID가 일치한다 | NOT VERIFIED |
| TEST-019 | SRS-019 | 키가 1개 프로젝트만 허용한다 | 다른 프로젝트 또는 전체 검색을 시도한다 | 검색 전에 권한 위반이 거부되고 결과가 누출되지 않는다 | NOT VERIFIED |
| TEST-020 | SRS-020 | 하나의 Item에 7개 Chunk가 매칭된다 | top_k=10 검색한다 | 고유 Item은 한 번만 나타나며 결과 수가 10개 Item 이하다 | NOT VERIFIED |
| TEST-021 | SRS-021 | 기본 응답 및 상세 반환 옵션이 있다 | 응답 옵션을 변경한다 | 기본은 경량이고 전체 필드는 명시된 옵션에서만 반환한다 | NOT VERIFIED |
| TEST-022 | SRS-022 | 본문 URL과 공식 Relation이 있다 | 검색 응답에서 관계 정보를 요청한다 | ID·관계만 반환하고 1/N-hop 본문 확장 또는 본문 URL 자동 연결은 하지 않는다 | NOT VERIFIED |
| TEST-023 | SRS-023 | Rev3 검색 중 Rev4 Index Stage가 실패한다 | 검색을 실행한다 | Rev3만 제공되며 Rev4의 partial chunk는 노출되지 않는다 | NOT VERIFIED |
| TEST-024 | SRS-024 | 새 embedding/chunker 설정이 적용된다 | 새 generation을 준비한다 | 완전성 검증 뒤 active 세대를 전환하고 이전 세대는 안전 정리된다 | NOT VERIFIED |
| TEST-025 | SRS-025 | 독립 stage에 유효한 중간 출력이 있다 | process 또는 index만 재실행한다 | 의존성을 검증한 뒤 관련 stage만 실행된다 | NOT VERIFIED |
| TEST-026 | SRS-026 | 두 프로젝트가 동시에 sync를 요청한다 | Job 큐를 실행한다 | 프로젝트별 FIFO 직렬 실행과 내부 제한 병렬이 유지된다 | NOT VERIFIED |
| TEST-027 | SRS-027 | 관리자와 읽기전용 API Key가 있다 | 권한 변경·호출·폐기를 수행한다 | Hash만 저장되며 권한 없는 쓰기나 프로젝트 접근이 거부된다 | NOT VERIFIED |
| TEST-028 | SRS-028 | ALM Secret 및 검색 Query가 있다 | API를 호출하고 로그·감사를 조회한다 | Secret/원문 Query는 기본 비노출되고 관리 변경은 감사에 기록된다 | NOT VERIFIED |
| TEST-029 | SRS-029 | 관리자로 Web UI에 접근한다 | 서버·프로젝트·Job·Explorer 화면을 탐색한다 | 권한 검증되며 HTML이 안전하게 표시된다 | NOT VERIFIED |
| TEST-030 | SRS-030 | 원본 SQLite·Qdrant·첨부 볼륨이 있다 | 백업 및 복구를 실행한다 | Manifest·상호 무결성을 확인하고 데이터가 보존된다 | NOT VERIFIED |
| TEST-031 | SRS-031 | 프로젝트에 여러 Revision·첨부가 있다 | Export 후 신규 환경 Import한다 | 원본 및 정규화 데이터가 보존되고 벡터는 재생성된다 | NOT VERIFIED |
| TEST-032 | SRS-032 | 동일 Item UID+Revision이 있고 Hash가 다르다 | Import 병합한다 | 충돌은 격리되고 기존 원본 및 삭제 상태가 덮이지 않는다 | NOT VERIFIED |
| TEST-033 | SRS-033 | 프로젝트에 수집 누락/인덱스 불일치가 있다 | Integrity 검사를 수행한다 | 누락과 불일치가 보고되고 개별 재처리가 가능하다 | NOT VERIFIED |
| TEST-034 | SRS-034 | Gold set이 제공된다 | dense/keyword/hybrid를 비교한다 | item-level Precision@K/Recall@K/MRR를 계산한다 | NOT VERIFIED |
| TEST-035 | SRS-035 | 계획 용량 100k Item을 생성했다 | Load 검증을 실행한다 | 용량/시간/에러율을 실제 수치와 함께 보고한다 | NOT VERIFIED |
| TEST-036 | SRS-036 | 사전 warm single-project 환경이다 | top_k=10 경량 검색을 반복한다 | P95<=3s를 실측하고 환경과 표본수를 기록한다 | NOT VERIFIED |
| TEST-037 | SRS-037 | CPU/GPU/Remote 임베딩 환경이 있다 | 동일 샘플을 실측한다 | chunks/s, tokens/s, batch 지연, 재임베딩률을 비교한다 | NOT VERIFIED |
| TEST-038 | SRS-038 | Windows/macOS/Linux 또는 Docker 환경이 있다 | Native/Compose 스모크 테스트를 실행한다 | 지원 조합별 PASS/FAIL/NOT VERIFIED 기록이 남는다 | NOT VERIFIED |
| TEST-039 | SRS-039 | 테스트 계획과 실행 결과가 있다 | Unit/Integration/Mock E2E를 수행한다 | 실패 및 미실행을 PASS라고 하지 않는다 | NOT VERIFIED |
| TEST-040 | SRS-040 | FastAPI, React 및 Worker 구성이 있다 | 작업과 조회를 동시에 수행한다 | API가 Worker로 인해 차단되지 않고 코드 공유 모듈을 사용한다 | NOT VERIFIED |
| TEST-041 | SRS-041 | Milestone 진행 중이고 QA 오류가 발생한다 | 재작업을 반복한다 | 최대 3회 후 중단하고 QA/PendingApproval을 준수한다 | NOT VERIFIED |
| TEST-042 | SRS-042 | 개발 산출물이 수정됐다 | Git 및 Notion 보고서를 갱신한다 | 문서/코드/테스트와 승인 이력이 연결되고 기밀은 외부 반출되지 않는다 | NOT VERIFIED |
| TEST-043 | SRS-043 | 최종 승인 요청 전 상태이다 | Main Agent가 M1 구현·GitHub Push를 시도한다 | 명시적 사용자 승인 전에는 실행하지 않는다 | NOT VERIFIED |

SRS-044~059: see `docs/testing/TEST_PLAN.md` dedicated table.

Milestone QA must implement executable tests for each relevant SRS and record actual evidence, test version, configuration and environment.
