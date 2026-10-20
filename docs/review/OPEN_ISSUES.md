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

## 로컬 개발 환경 사전 검증 추기 — 2026-10-19

상세 증거: [CODEX_PREFLIGHT_REPORT.md](CODEX_PREFLIGHT_REPORT.md). 기존 컨테이너 관찰과 현재 로컬 상태를 구분한다.

| ID | 관찰 / 남은 조치 | 상태 |
|---|---|---|
| OI-027 | 기본 python3=3.9.6에서 tomllib 오류(exit 1); 설치된 Python 3.12.12에서도 PyYAML 누락(exit 2). 검증 환경 준비 후 Baseline 재실행 필요 | FAIL; 전체 정적 Baseline NOT VERIFIED |
| OI-028 | Docker/Compose PATH 미발견, Docker.app 없음. 로컬 Node 25와 초안 Node 22 기준 차이. 도구 경로/버전 정리 필요 | Docker 가용성 FAIL; Build/Boot NOT VERIFIED |
| OI-017 / OI-022 / OI-025 | CLI 0.163.0, multi_agent=true, 6개 역할 TOML/등록 PASS. qa spawn/지시 전달 PASS. 다른 5개 역할 실행, 동시 제한, Worktree 경합 및 포괄적 Sandbox 실효성은 미검증 | PARTIAL / NOT VERIFIED |
| OI-008 / OI-024 | 현재 origin URL은 설정됨. 로컬 origin/main과 HEAD 동일. 원격 최신성/비공개 여부/접근권한/Push 별도 승인은 확인하지 않음 | 설정 존재 PASS; 원격 검증 NOT VERIFIED |
| OI-026 | 로컬 원격 추적 참조 존재만으로 원격 동기화 성공을 재판정하지 않음. Notion 자동 발행 미구현 상태 유지 | NOT VERIFIED / NOT IMPLEMENTED |

### 환경 보완 재검증 — 동일 날짜, 최초 결과를 대체하는 최신 상태

| ID | 후속 증거 | 최신 상태 |
|---|---|---|
| OI-027 | Python 3.12.12 `.venv` + PyYAML 6.0.3 준비. 활성화 후 동일 Baseline 스크립트 exit 0, DOC_STATIC_PASS | RESOLVED for documented environment; 시스템 Python 3.9 유지 |
| OI-028 | Node 22.23.3 설치/세션 PATH 선택. Docker CLI/Compose/Colima 설치, Compose config exit 0, 전용 VM의 hello-world exit 0 | 도구/단일 컨테이너 PASS; 앱 Build/Boot NOT VERIFIED |
| OI-017 / OI-022 / OI-025 | 6개 역할 모두 실제 spawn 및 역할 지시 전달 확인 | 역할 smoke PASS; 동시 상한/Worktree 경합/포괄적 Sandbox 강제성 NOT VERIFIED |

M1 착수 승인, 원격 Push 승인, Legacy 원문 및 외부 통합 관련 미결사항은 해소된 것으로 간주하지 않는다.

## M1 착수 후 상태 — 2026-10-19 승인 / 2026-10-20 계속 진행

- OI-009: 사용자의 “커밋반영하고 착수해”로 M1 시작 승인. M1 완료 승인과 M2 시작 승인은 아직 없음. BASELINE_APPROVAL.md와 M1/PLAN.md 참조.
- OI-029: 실패 Item 목록 권한이 OpenAPI(project_read)와 FAIL_SAFE_AND_REPLAY(project_manage)에서 불일치. M1은 schema 기반만 구현하고 해당 route는 미구현 유지. 해당 route 구현 전 권한 정책 확정 필요; 정책을 자동 변경하지 않음.
- OI-030: 실제 앱 Windows/macOS/Linux 전체 매트릭스, 외부 모델/Qdrant/ALM 검증은 개별 실행 증거 전 NOT VERIFIED. 환경 smoke PASS를 제품 검증으로 승격하지 않음.
- OI-031: 초기 Frontend dev 의존성 npm audit: @vitest/mocker Moderate, tinypool/vitest Critical, 총 3 affected packages. AGENTS Critical stop에 따라 M1 BLOCKED, Human Review 필요. 제안: Vitest 5.0.5와 호환 tooling으로 명시적 갱신 후 lock/audit/Red-Green/build 재검증. QA_REPORT.md 참조. 아직 수정/위험 수용 승인 없음.
- OI-032: Python runtime cryptography 46.0.7의 7 advisory entries는 50.0.2로 갱신, frozen runtime pip-audit 재실행 exit 0. RESOLVED for current scan; 미래 취약점 부재 보장 아님.

### M1 최종 로컬 검증 상태 — 2026-10-20

- OI-031 RESOLVED: 사용자 “진행해”로 보완 승인. Vitest5.0.5/새 lock, npm audit0, clean install/6테스트/build 및 Frontend 컨테이너/실브라우저 smoke PASS.
- OI-014 PARTIAL: Python/Node lock과 언어 패키지 audit, macOS Native 및 Linux-arm64 API/Worker/Frontend Build/Boot PASS. Windows/native Linux/AMD64 및 이미지 OS계층 보안 스캔은 NOT VERIFIED.
- OI-016 M1 FOUNDATION PASS: SQLite WAL/FK/transaction, 다중 프로세스 단일 claim, 강제종료 checkpoint/lease fencing 검증. 실제 SQLite/Qdrant 게시 정합성은 M4/M6 NOT VERIFIED.
- OI-018 M1 FOUNDATION PASS: 실제 Red/Green 문서와 요구사항 연결, 로컬 CI 동등 검사 PASS. 원격 CI 실행 NOT VERIFIED.
- OI-009: M1 시작/보완은 승인됨. M1 완료는 PENDING_APPROVAL, M2 미착수.
- OI-019/OI-023 및 OI-029 권한 문서 충돌은 열린 상태 유지. M1에 미구현인 failed-item route의 정책을 임의 선택하지 않았음.
- OI-033: 이 로컬 Python 배포에서 stdlib venv의 ensurepip가 SIGABRT로 중단됨(일반/elevated 동일). 표준 개발 경로인 uv venv + 오프라인 wheel 설치·migration은 PASS. stdlib ensurepip 원인 분석은 환경 backlog이며 uv 실행경로를 막지 않음.
