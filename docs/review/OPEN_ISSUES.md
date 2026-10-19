# Open Issues / Validation Backlog

| ID | Issue | Owner at milestone | Gate |
|---|---|---|---|
| OI-001 | Codebeamer 서버 버전/Swagger/읽기 권한 확인 | M2 Collector | 실제 ALM integration NOT VERIFIED until checked |
| OI-002 | Polarion 서버 버전/processed HTML 제약 확인 | M2 Collector | 저장된 HTML과 실제 화면 차이 검증 |
| OI-003 | Notion/GitHub 외부 데이터 반출 정책 | M1 Architect/Security | 수집 원문 업로드 기본 금지 |
| OI-004 | Hybrid BM25 engine 및 한글·자동차 토큰 분석기 | M4 RAG Engineer | 성능·정확도 비교 후 ADR |
| OI-005 | Staged index active_revision concurrency/crash tests | M4+M6 QA | 강제 품질 Gate |
| OI-006 | HTML Table 보존 및 fallback acceptance oracle | M3 QA | Merge/Rowspan 검증 케이스 |
| OI-007 | Remote Ollama/Qdrant 연결과 비용/하드웨어 | M1/M6 | env-specific tests |
| OI-008 | GitHub private repository owner/repo URL 미제공 | User | GitHub Push 전 |
| OI-009 | v0.3 조건부 Baseline 승인됨; M1 코드 구현은 별도 명시적 착수 지시 전 금지 | User | M1 시작 전 |

## v0.2 세부 검토 Backlog
| ID | Issue | Owner | Gate |
|---|---|---|---|
| OI-010 | CB 3.x 버전별 Project/Tracker 상세/필드 API 호환성, 인증 방법 | M2 Collector | 실제 Server 미검증 |
| OI-011 | Polarion Project Work Item Type enumeration / Rich Text source HTML / Scope 미리보기 | M2 Collector | 실제 Server 미검증 |
| OI-012 | EmbeddingGemma 2 runtime 모델 tag/digest, 토큰 계수·실제 context/truncation | M3 RAG Engineer | M3 시작 전 테스트 Fixture |
| OI-013 | Target 512/max 1024/overlap64에서 골든셋 Retrieval 품질 최적화 | M3/M6 QA | 수치는 튜닝 후보 |
| OI-014 | Docker runtime/Node/Python lock+security Scan 및 실제 Native cross-platform 검증 | M1/M6 | Skeleton 상태 NOT TESTED |
| OI-015 | 서버별 제한 Rate 실측 및 429 Retry-After/전역 pause policy | M2 | 운영 서버 영향 최소화 필수 |
| OI-016 | 단일 SQLite에서 API/Worker concurrency, checkpoint/replay 강제중단 검증 | M1/M4 | DB/Qdrant 정합성 Gate |
| OI-017 | Codex CLI 버전별 multiagent 등록/Worktree/격리 지원 확인 | 개발 착수 Preflight | 기능 확인 전 자동 병렬 가정 금지 |
| OI-018 | TDD Red/Green Evidence 저장 포맷과 CI/QA 게이트 구성 | M1 | Doc-only 단계 NOT TESTED |

## v0.3 Baseline Audit 추가 미결사항
| ID | 이슈 | Gate / 책임 | 상태 |
|---|---|---|---|
| OI-019 | 원본 REQ-001~252 모든 개별 문장 미보유; 9개 번호 결정 요약 미연결 (REQ-001, REQ-003, REQ-004, REQ-005, REQ-006, REQ-007, REQ-008, REQ-009, REQ-010). 남은 번호도 Clause별 정합성 미증명 | Requirements Agent, Baseline User Gate | NOT VERIFIED |
| OI-020 | OpenAPI `200/202` 응답 중 목록 페이지네이션, 인증 상태, 백업/임포트의 상세 스키마 일부 정의 필요 | M1 Backend Architect / M5 QA | PLANNED |
| OI-021 | Active Revision + Index generation 전환/조회 중 Snapshot 및 overfetch bound · multi-project generation 조회 계약 정량 시험 필요 | M4 RAG Engineer, M6 QA | NOT VERIFIED |
| OI-022 | Codex CLI 실제 버전/Agent role config/Worktree 경합 검증 및 승인 정책 샌드박스 실효성 확인 | Before M1 | NOT VERIFIED |
| OI-023 | 사용자 2026-10-19 조건부 승인: 원본 REQ-001~252 Clause 단위 검증 미완료 상태로 유지, 59개 SRS 및 결정 50개는 개발 기준으로 인정 | Requirements Agent | ACCEPTED AS OPEN / NOT VERIFIED |

## v0.3 조건부 승인 이후 운영상 미결사항
| ID | 이슈 | 책임 / 다음 단계 | 상태 |
|---|---|---|---|
| OI-024 | Private GitHub repository 소유자, 원격 URL, 접근권한 및 생성/Push 별도 확인 필요 | User / GitHub 연결 | NOT CONFIGURED |
| OI-025 | 로컬 사용자 Codex CLI 버전과 6개 role spawn/Worktree 충돌/approval sandbox 테스트 | 사용자 실제 실행 환경, M1 전 | NOT VERIFIED |
| OI-026 | 기준선 ZIP/로컬 Git Commit은 생성됐지만 GitHub 원격 동기화와 Notion 자동 발행은 미구현 | M1/M5, 별도 승인 | NOT IMPLEMENTED |
