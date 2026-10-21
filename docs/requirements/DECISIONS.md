# 사용자 확정 결정 기록 (Questions 01–50)

기준일: 2026-10-19. 이 문서는 대화에서 사용자가 **명시적으로 선택한 최종안**을 정리합니다.

| 질문 | 최종안 | 결정 | 적용 단계 | 원래 요구사항 식별자 |
|---|---|---|---|---|
| Q01 | A | Polarion은 Work Item만 수집; LiveDoc 일반 텍스트 제외 | M2 | REQ-002 |
| Q02 | B | 첨부파일 다운로드·원본 보존, 내용 임베딩 제외 | M2 | REQ-011 |
| Q03 | B | Title+Description+선택된 Custom Fields 임베딩 | M3 | REQ-012 |
| Q04 | B | 최초 최신 Revision; 이후 관측된 변경 Revision 보존 | M2 | REQ-013 |
| Q05 | B | 최초 전체 수집 + 수동 증분 동기화 및 선택적 재임베딩 | M2/M3 | REQ-014~019 |
| Q06 | B | Custom Field별 독립 Chunk; 모든 Chunk에 동일 item_uid; Item 단위 반환 | M3/M4 | REQ-020~023 |
| Q07 | B | Dense Vector + Keyword BM25 계열 Hybrid Search/RRF | M4 | REQ-024~027 |
| Q08 | B | 여러 ALM/프로젝트를 저장; 지정한 단일·다중 프로젝트만 검색 | M1/M4 | REQ-028~036 |
| Q09 | C | 프로젝트별 전체 수집 또는 Tracker/Work Item Type 선택 수집 | M2 | REQ-037~040 |
| Q10 | B | 삭제된 Item 원본/이력 보존, 기본 검색 제외 | M2/M4 | REQ-041~043 |
| Q11 | B+옵션 | 검색 Item 전체·매칭 Chunk·점수 선택적 반환; 경량 기본 | M4 | REQ-044~048 |
| Q12 | B | top_k는 고유 Item 개수; 기본 10, 허용 1~100 | M4 | REQ-049~052 |
| Q13 | B | 골든셋 기반 Precision/Recall/MRR와 검색 방식별 평가 | M6 | REQ-053~057 |
| Q14 | B | HTML 원본, 정규화 텍스트, Table JSON; 본문/표 독립 Chunk | M3 | REQ-058~063 |
| Q15 | C | CLI + 관리/검색 REST API + React Web UI | M1/M5 | REQ-064~068 |
| Q16 | D | Windows/macOS/Linux 공통 지원 | M1/M6 | REQ-069~072 |
| Q17 | C | Docker Compose와 Native 실행 모두 지원 | M1/M6 | REQ-073~076 |
| Q18 | B | Ollama와 Qdrant 각각 로컬/원격 연결 지원 | M1 | REQ-077~081 |
| Q19 | B | Web UI ALM 등록 + 암호화/OS 보안 저장소; 환경변수 허용 | M1/M2 | REQ-082~087 |
| Q20 | B | ALM API 자동 프로젝트/Tracker/Type 탐색 + UI 수집대상 선택 | M2/M5 | REQ-088~093 |
| Q21 | B | ALM/첨부/파서/임베딩/업서트별 제한된 병렬성 설정 | M2/M3 | REQ-094~099 |
| Q22 | B | Item 단위 게시 + 체크포인트 재개; 실패 시 이전 검색판 유지 | M1/M3/M4 | REQ-100~105 |
| Q23 | B | 수집/처리/임베딩/인덱스 독립 실행 + 통합 실행 | M1/M2/M3/M4 | REQ-106~111 |
| Q24 | B | 신규 인덱스 격리 구축·검증 후 활성 전환 | M4 | REQ-112~117 (후속 변경 있음) |
| Q25 | A | 신규 인덱스 활성화 후 이전 인덱스 삭제; 영구 롤백 미지원 | M4 | REQ-118~122; REQ-117 수정 |
| Q26 | A | 프로젝트 간 작업은 FIFO 순차 실행; 프로젝트 내부 제한 병렬 | M1/M5 | REQ-123~127 |
| Q27 | B | Web 관리자 계정 + 프로젝트/권한별 API Key | M1 | REQ-128~133 |
| Q28 | B | 로컬 저장 + 수동/자동 백업 및 무결성 확인 복구 | M5 | REQ-134~139 |
| Q29 | B | Item 원본/정규화 정보 및 첨부 Export·Import; 임베딩은 재생성 | M5 | REQ-140~145 |
| Q30 | B | Import 시 item_uid+Revision+Hash 기반 병합; 충돌 분리 | M5 | REQ-146~151 |
| Q31 | B | Item/HTML/Table JSON/Chunk/Hash/상태 상세 조회 UI; 직접편집 제외 | M5 | REQ-152~158 |
| Q32 | C | HTML/Table 변환 Fallback, 정보 검증 실패 시 현재 활성 검색판 유지 | M3 | REQ-159~164 |
| Q33 | A | 본문 원본 링크 보존; ALM 공식 관계 별도 수집; 본문 링크 자동 UID 매핑 제외 | M2/M3 | REQ-165~169 |
| Q34 | A | 검색 Item만 반환; 관계 대상 ID만 옵션 제공; 1/N-hop 확장 제외 | M4 | REQ-170~174 |
| Q35 | B | 단계별 수집/필드/첨부/Chunk/SQLite-Qdrant 정합성 검증 | M6 | REQ-175~180 |
| Q36 | B | 구조화 JSON 로그, 운영 메트릭, 접근/변경 감사 로그 | M1/M5 | REQ-181~187 |
| Q37 | B | ALM Item 약 10만 개 목표 | M6 | REQ-188~190 |
| Q38 | B | Warm·단일 요청·top_k=10·경량 결과 P95 3초 이내 목표 | M6 | REQ-191~196 |
| Q39 | B | CPU/GPU/원격별 임베딩 실측·최적화; 고정 throughput 목표 없음 | M6 | REQ-197~202 |
| Q40 | B | Unit+Integration+Mock E2E 자동 테스트 및 요구사항별 증거 | M1~M6 | REQ-203~208 |
| Q41 | B | FastAPI+React TS+독립 Worker Modular Monolith | M1 | REQ-209~214 |
| Q42 | B | M1~M6 Milestone 내부 Autopilot·종료 후 사용자 승인 | M1~M6 | 실행 정책 |
| Q43 | B | Main 1 + Requirements/Architect/Collector/RAG/Frontend/QA 6개 전문 Subagent | M1~M6 | 역할 정책 |
| Q44 | B | Git Worktree 기반 병렬 구현, Main 통합, QA, Human Gate | M1~M6 | REQ-215~220 |
| Q45 | C | SRS/SAD/SDD/API/ADR/시퀀스/데이터흐름/테스트·추적성 상세 문서 | M1~M6 | REQ-221~228 |
| Q46 | B | 자동 Quality Gate + Human Approval; PASS/FAIL/NOT VERIFIED | M1~M6 | REQ-229~235 |
| Q47 | B | 자동 수정·QA 재검증 최대 3회, 중대한 이슈 즉시 중단 | M1~M6 | REQ-236~241 |
| Q48 | B+Notion | Codex 승인+Git 산출물+Notion 별도 보관공간, 알림·승인 이력 | M1~M6 | REQ-242~248 |
| Q49 | B | 로컬 Git+Private GitHub, 원격 Push·시크릿 유출 방지 | M1 | REQ-249~252 |
| Q50 | B | SRS/SAD/API/계획/Agent 설정 패키지 및 검토 보고서 생성 후 승인하고 개발 시작 | 준비 단계 | 개발 착수 게이트 |

## 우선순위와 변경 처리
- Q09는 마지막 선택 **C**가 유효하며 이전 B 선택은 폐기됩니다.
- Q25의 A 선택은 Q24의 인덱스 교체 정책에 우선합니다. 이전 인덱스 삭제 후 영구 롤백은 지원하지 않습니다.
- Q33의 A 선택은 **본문 링크 자동 참조 매핑을 제외**하지만 ALM 공식 Link/Relation 수집은 유지합니다.
- Q34의 A 선택은 연결된 관계 대상의 전체 본문 확장을 제외합니다.
- Q48은 B안에 **Git+Notion 기록과 사용자 알림**을 추가한 최종안입니다.
- 역사적인 REQ 번호는 대화에서 작성된 추적 식별자입니다. 서로 범위가 중복되거나 초안에만 등장한 일부 번호는 이 문서에서 재정의하지 않습니다. 최종 구현 추적에는 별도 `SRS-xxx` 번호를 씁니다.

## 사용자 추가 결정: 사내 HTTP 운영 검증

사용자가 사내 사용에 HTTPS를 적용하지 않으며 남은 실무 실행 기능을 구현하고 Linux 실서버에서 실제 ALM·DB·Ollama 연동을 검증하도록 명시했습니다. 기본 HTTPS 보안 설정은 유지하고 `ALMRAG_INTRANET_HTTP_ENABLED=true` 및 정확한 HTTP Origin을 지정한 환경만 HTTP 관리자 세션을 허용합니다. HttpOnly·SameSite·CSRF·Origin·프로젝트 ACL은 유지합니다. HTTP 구간의 로그인/세션/API 통신은 암호화되지 않으며 해당 사내 네트워크에서 사용합니다. 실제 접속 결과는 수행 전까지 NOT VERIFIED입니다. 원본 DB는 승인된 SQLite이며 외부 SQL DB 제품 지원으로 범위를 확대하지 않습니다.
