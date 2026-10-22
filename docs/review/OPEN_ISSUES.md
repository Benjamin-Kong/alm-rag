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
- OI-034: 시스템 기본 Node25.8.0이 simdjson dylib 불일치로 중단됨. 프로젝트 Node22 PATH에서 Codex0.163.0/feature 조회 PASS. 전역 Node 환경 수리는 별도 환경 backlog; M2는 지정된 Node22 사용.
- M1은 사용자 2026-10-20 승인됨(13e1f30). M2 시작 승인; M2 완료/M3는 별도 Human Gate.

### M2 구현 중 독립 QA 중단 — 2026-10-20 (최신 상태)

- **OI-035 / Major / OPEN:** 큰 429 본문이 응답 크기 제한에 먼저 걸려 Retry-After 전역 pause가 저장되지 않음. Mock 실제 재현: Retry-After15초, 본문100바이트/제한10바이트 → pause_until=0, 다음 요청1000.2초(요구>=1015초). 동일 처리 순서의 401 영향은 코드 추론이며 별도 재현 미실행. SRS-053/054. M2/QA_REPORT.md 참조.
- **OI-036 / Major / OPEN:** timeout+5초 permit이 활성 스트림 종료 전에 만료됨. Mock 실제 재현: max_inflight1/timeout1초/전체예산100초,7초 경과 후 두 번째 요청 허용 → 동시 스트림2. SRS-053/054.
- **OI-037 / Minor / OPEN:** 전체예산1초에도2초 후 빈200 응답을 성공 반환. acquire/응답 완료 시 deadline 검증 필요. SRS-053/054.
- AGENTS.md의 unresolved Critical/Major 즉시중단 규칙 적용: M2 BLOCKED_FOR_HUMAN_REVIEW. 구현/통합/수정 작업 중단, 두 specialist worktree 보존. 기존10테스트 PASS는 위 결함 해소나 M2 완료 증거가 아님. 사용자 검토 후 수정 재개 승인 필요.

### M2 수정 재개 후 추가 통합 발견 — 2026-10-20

- 사용자가 “수정안을 적용하고 계속진행해”로 OI-035/036/037 보완과 M2 재개를 승인함. 해당 Transport 수정은 별도 Worktree에서 실제 Red/Green으로 진행; 최종 통합/QA 결과는 M2/TRANSPORT_TDD.md 및 QA_REPORT.md 최신 추기 참조. 과거 FAIL 기록은 삭제하지 않음.
- **OI-038 / Major / OPEN:** 실제 Codebeamer 어댑터의 첫 Item customFields 형식 오류가 전역 INVALID_SOURCE_PAYLOAD로 분류됨. 두 Item Mock 실측: preflight READY → Job BLOCKED, 정상 두 번째 Item 미요청, 실패 큐0/저장 Revision0. SRS-055 및 FAIL_SAFE_AND_REPLAY의 Item 필드 변환 오류 격리 정책 위반. 인증/페이지/Scope/저장소 무결성 실패가 아닌 Item 변환 오류만 로컬 격리하도록 경계 보완 필요. 새로운 Major 확인 후 추가 구현 중단; 별도 Human Review 필요.
- **OI-039 / Medium / OPEN:** 예상 요청량이 부가 관계/첨부/Scope 재검증 호출을 누락. 합성1 Item에서 예상6/실제8. 확정치로 표시 금지; 보수적 산정 또는 하한·불확실성 명시 필요.
- **OI-040 / Medium / OPEN:** FieldDefinition UID에 CB Tracker Scope가 없어 동일 프로젝트의 Tracker별 같은 필드ID가 합쳐질 수 있음. 원본 envelope는 보존되지만 메타데이터 식별자 보완 필요.
- **OI-041 / Integration / OPEN:** Codebeamer 숫자형 원본 Field ID와 normalized title/description 정책을 직접 비교하여 기본 Preflight가 BLOCKED. 원본 catalog ID를 변경하지 않고 normalized 필드 네임스페이스를 별도로 명시해야 함. Main API 통합 테스트2건은 현재 FAIL,3건 PASS; 완료 주장 없음.
- 실제 커넥터는 deleted bool 외에 확정 deletion_evidence를 제공하지 않으므로 삭제 확정 수집 능력은 NOT VERIFIED/미지원. Stub의 명시적 삭제 테스트 PASS를 실제 어댑터 삭제 검증으로 간주하지 않음.
- **OI-035/OI-036/OI-037 RESOLVED for tested local scope:** Main 반영 후 독립 QA20테스트 PASS(1.34s), Main 관련92PASS. 오류 헤더 우선 저장/활성 OS slot 소유권/프로세스 사망 회복/빈응답 deadline 확인. Linux/Windows·공유파일시스템·실제socket hard interruption은 NOT VERIFIED. M2 전체132PASS/3FAIL이며 OI-038 새 Major로 BLOCKED 유지.

### M2 최종 로컬/Mock 검증 — 2026-10-20 (위 중간 상태를 대체하는 최신 상태)

- **OI-038/039/040/041 RESOLVED within local/mock scope:** 사용자 “보완하고 계속 진행해” 후 실제 실패12건을 Main에서 확인하고 보완. 두 제품 Item 필드/본문/관계 변환 오류는 실패 큐로 격리하고 정상 형제 Item 계속 처리. 원본 catalog와 normalized 필드 분리, Tracker별 field UID, 명시적 UNKNOWN 요청량/하한, 정책 fingerprint 검증. 실제 서버/전체 요청량 확정값은 여전히 미검증.
- **OI-042 / Major / RESOLVED:** 동등 URL의 기본443/80이 다른 server key로 전역pause/lock을 우회하던 독립 QA 재현. 사용자 “진행중인가? 계속 구현해” 이후 회귀 Red4FAIL→보완. 프로필/정책/allowlist/전역budget/lock에 HTTPX 기준 canonical origin 적용, 원래 재현 및 독립 QA PASS. 기존 비정규 prototype budget은 SERVER_ORIGIN_MIGRATION_REQUIRED로 fail-closed; 실제 상태 병합/삭제/lock 이전은 자동 수행하지 않음.
- **OI-043 / Minor / RESOLVED:** Worker가 ALMRAG_ATTACHMENT_ROOT를 무시하던 문제. 실제 Red2FAIL→공통 Settings.attachment_directory로 API/Worker 일치; 기본은 DB volume 내부. 독립 QA PASS.
- **OI-044 / Minor / RESOLVED:** 잘못된 포트 입력에서 httpx.InvalidURL이 검증기를 벗어나500. 실제 Red1FAIL→ValueError로 매핑→422 INVALID_REQUEST, 등록0/외부요청0; 독립 QA 새1테스트 PASS.
- **OI-045 / Process exception / OPEN FOR USER REVIEW:** 최초 connection/config 프로필 prototype을 테스트보다 먼저 작성함. 후속 경계/결함 수정 Red→Green은 있지만 최초 chronology는 TDD_NOT_EVIDENCED. TEST-058 PARTIAL; 기록 삭제/사후 조작 없이 M2 Human Gate에서 예외 검토 필요.
- 최신 실제 Main: Python178PASS, Frontend7PASS/build, 두 이미지/세서비스 healthy, network-none 수집 smoke39 합성GET, wheel migrations[1,2,3], Python/Node dependency audit0. 독립 QA full177PASS + 마지막 신규minor1PASS. 알려진 미해결 code Major/Critical 없음; M2 PENDING_APPROVAL, M3 미착수.
- OI-001/002/010/011/015 실서버 및 확정 삭제/렌더링 안전, OI-019/023 Legacy 원문, OI-029 public replay ACL 충돌, OI-030 다중플랫폼/OS image scan, 원격 CI/Push/Notion은 OPEN/NOT VERIFIED 유지. Source 관측 안전을 실제 ALM 기능 완전 검증으로 승격하지 않음.

### M3 checkpoint — latest,2026-10-20

- M2 approved at0b38393 by subsequent user “계속진행해”; OI-045 accepted as retained TDD_NOT_EVIDENCED process exception, never retroactively PASS. M3 started on codex/m3-content.
- **OI-046 / Major / RESOLVED in tested scope:** HTML recover parser dropped deep/huge input after FATAL resource limit; source retained but derived output incomplete. Actual Red1FAIL, Item-local HTML_PARSE_INCOMPLETE correction; independent300deep/>10MB repro rejected and49target testsPASS.
- **OI-047 / Major / OPEN:** LocalTokenizer preserves artifact truncation/padding;2000 tokens count8, one token count16/32. Independent complete chunk repro actual2008>1024 but metadata8. Model truncate:false/count check mitigates accepted truncated vectors, no source loss demonstrated. Actual new regressions2FAIL; implementation stopped. See M3/QA_REPORT.md and unapplied TOKENIZER_FIX_PROPOSAL.patch. Human Review required before correction/resumption under AGENTS.
- Main264PASS preceded OI-047 regressions; current tree is not all-green. Frontend8PASS/build, packagebuild/static3.12PASS. Real model/ALM/M3Docker and wheelisolatedinstall/fullmockE2E/remoteCI remain NOT VERIFIED. M3 incomplete and uncommitted, M4 not started.

### M3 tokenizer correction revalidation — latest,2026-10-20

- **OI-047 / Major / RESOLVED within local tested scope:** user “수정안 적용하고 재검증해” approved the saved proposal. LocalTokenizer explicitly disables artifact truncation/padding, preserves special tokens and source checksum, versions its identity. Actual Red3FAIL (including exact15k-token full-input chunk bounds/coverage)→focused62PASS6.35s→full267PASS22.58s. Independent43PASS1.72s and original long/padded-input repro corrected; oldprofile mismatch and modelcount checks remain fail-closed. See M3/TOKENIZER_REVALIDATION.md.
- Frontend8PASS/build and project Python3.12 static gate PASS. No remaining Critical/Major identified in the bounded correction review. M3 resumes IN_PROGRESS; full mockE2E/container/wheel isolated install/final traceability/realmodel remain NOT VERIFIED. M3 completion/M4 are not approved; no remote action performed.

### M3 final local candidate — latest,2026-10-20

- OI-046/OI-047 remain RESOLVED within tested local scope. Main271PASS33.68s; independentQA271PASS33.18s; Frontend8PASS/build. No confirmed remaining code Critical/Major identified. Mock E2E4PASS includes15k+100row retention, zero-repeat embedding and100Items/3parser failures→97ready/all100raw.
- M3 packaging/isolated wheel schema1..4, updated current contract/type-client/negative ACL, Python/Node audit0, local images/threehealthyservices, network-none runtime55chunks13content requests repeat0 and M2regression39GET PASS. Test services stopped; volumes retained. SRS assignments unchanged10Primary+7Shared; see M3/M3_TRACEABILITY.csv and GATE_MATRIX.md.
- **OI-048 / Runtime verification / OPEN-NOT VERIFIED:** actual embeddinggemma-2 model/tokenizer artifacts and deployed context/digest/calibration/vector quality were not exercised. All runtime evidence FIXTURE_ONLY; no auto-download, live model disabled, unverified runtime BLOCKED. M3 acceptance must retain this limitation. It is not a claim of safe actual-model token accounting.
- OI-019/023 original legacy clauses, OI-029 public replay ACL conflict, OI-030 platform/image-OS/remoteCI and actual ALM/renderer/deletion limits remain OPEN/NOT VERIFIED. M2 OI-045 accepted TDD exception retained. Full SYNC/active search/detail/Qdrant/public replay belongsM4 and notclaimed.
- M3 PENDING_APPROVAL_WITH_DOCUMENTED_LIMITATIONS; M4 not started. No Push/Notion/liveALM/model/productiondeployment. User must approve the completion candidate before next milestone.

## M4 permission clarification — 2026-10-20

- OI-029: RESOLVED by explicit user decision “목록 조회는 project_read 허용”. GET failed-items uses project_read; retry/retry-all/resume use project_manage. FAIL_SAFE_AND_REPLAY.md is aligned with OpenAPI. Earlier OPEN entries above remain historical evidence; runtime negative ACL verification is recorded separately in M4 evidence.

## M4 independent QA Human Review — latest, 2026-10-20

- **OI-049 / Major / OPEN-HUMAN_REVIEW_REQUIRED:** SRS-018 exact Item ID retrieval is absent. Independent synthetic published source ID ALM-EXACT-987654 (not in title/body) returns no keyword hit; typed ID filter is rejected. Existing166PASS21.63s does not prove this missing feature. Main stopped implementation immediately. See M4/QA_REPORT.md and CORRECTION_PROPOSAL.md; user corrective approval required before resuming.
- OI-029 remains RESOLVED by explicit list=project_read decision; retry/resume retain project_manage. API/CLI integration26PASS5.17s reached Main before STOP; isolated frontend10PASS but build FAIL awaiting new schemas. M4 API export/client synchronization and final acceptance remain NOT VERIFIED. No M4 completion or M5 authorization inferred.

## M4 corrective revalidation — latest, 2026-10-21

- **OI-049 / RESOLVED within local tested scope:** explicit approved correction implements exact source/internal IDs including metadata-only zero-Chunk publications, typed stored-field/scope filters, both-channel prelimit allowlists, generation lexical version/rebuild guard, API/client/CLI parity. Independent final417PASS64.63s includes5real syntheticQdrant tests; no confirmed remaining Critical/Major in bounded core/API review. Scope metadata and zeroChunk edge corrections each had actual Red before Green and independent recheck. Prior FAIL/HumanReview entries remain historical.
- **OI-050 / Dependency advisory / corrective work:** actual pip-audit found certifi2026.10.18 GHSA-6q48-6c7w-9gw2, fixedversion2026.10.19. uv lock upgraded exactlycertifi, uv sync installedfix; audit/image revalidation evidence in M4/TEST_REPORT.md. Advisory https://github.com/advisories/GHSA-6q48-6c7w-9gw2 . No liveALM/model was contacted.
- User explicitly authorized sequential M4→M5→M6 without further milestone/corrective approval prompts; quality gates and external restrictions remain. OI-048 realmodel/tokenizer and earlier actualALM/otherplatform/remoteCI limits remain OPEN-NOT VERIFIED.

## M5 corrective review — 2026-10-21

- OI-051 / Major / RESOLVED locally: reject cross-project field/relation namespace poisoning before any package publication/import write.
- OI-052 / Major / RESOLVED locally: seed exact source_latest and collection inputs for offline imported/recovered PROCESS/EMBED/INDEX; preserve newer current target and active publication.
- OI-053 / Major / RESOLVED locally: validate/read/capture outside long writer locks, fence short publication and renew atomic merge lease; slow-operation heartbeat adversarial tests pass.
- OI-054 / Major / RESOLVED locally: writer ZIP entry/expanded-size budgets agree with reader; reject own unreadable artifacts before publication.
- OI-055 / Major / RESOLVED locally: worker heartbeat ignores verified own-terminal state only at matching retry_count; replacement-finished stale owner still revoked.
- OI-056 / UI corrective / RESOLVED locally: stale SOURCE fields reset, empty filters omitted, original fallback owner verified and forbidden/500 never bypassed, SVG/preview bounded.
- OI-057 / Browser corrective / RESOLVED locally: native fetch receiver binding and exact control accessible labels;24units/build and7actualChromiumE2E PASS.

See M5 TDD/QA/TEST reports for original FAILs and independent rechecks. OI-019/023 legacy clauses, OI-030 platform/CI/image scanner, OI-048 actual model and actual ALM/provider integration remain NOT VERIFIED. Remote Notion provider implemented and mock tested but actual publication remains NOT VERIFIED and disabled. No Git remote Push or production deployment performed.

## M6 independent review and corrections — 2026-10-21

- OI-058 / Major / correction verified locally: strict original JSON integrity previously conflated bool/int and int/float including nested values. Four actual Reds→strict recursive JSON equality; independent original bool/int reproduction now reports FAIL as required.
- OI-059 / Integrity evidence / correction verified locally: durable quality request now immutable and canonical snapshot_hash checked before execution; explicit simulated corruption detected. Stage logging now includes all implemented quality/operations/replay stages.
- OI-060 / Major / RESOLVED within independently tested local scope: same-length normalized text/table-cell corruption and empty source spans were not detected. Three actual Reds→fresh normalization comparison, full source-inventory coverage and chunk content hash checks. Bounded affected Item/revision identifiers and explicit recovery/rebuild actions added; reports never silently repair live storage.
- OI-061 / UI corrective / resolved locally: browser Unicode-v credential pattern escaped; delayed dataset/job responses guarded by form revision. Actual failing tests before corrections, frontend28PASS/build. Native HTTPS fixture static dispatch corrected without changing product auth/ACL.

## M6 final local quality state — 2026-10-21

- OI-058/059/060/061 RESOLVED within tested local scope. Independent61target/46performance-target,1actualQdrant and final506PythonPASS77.45s/noSKIP; frontend28/build and root10ChromiumPASS8.2s. No unresolved confirmed Critical/Major in bounded independent review.
- OI-062 / Scale/performance / RESOLVED for synthetic exact-ID workload, real-model target NOT VERIFIED: first100k/199999Chunk P954.301s missed synthetic3second comparison. Actual SQL-work Red isolated fullgenerationpointscan; publication→membership→unique point lookup fixed it. Identical final100queryP951.37495s/alltop10/exactfirst100/100, rawinitialFAIL retained. See M6/BENCHMARK_REPORT. Generated1/2/3Chunk retrieval-shape fixture is not production-valid processing/integrity100k pipeline; actualOllama/Korean-semantic/modelCPU-GPU-remote benchmarks remain NV.
- Local M1..M6 implementation sequence is quality verified under explicit user continuation approval. Actual ALM/model/calibration/remote provider/delivery, production100kpipeline, other host OS/amd64/remoteCI/OSscanner limitations remain OPEN-NOT VERIFIED. Original legacy clauses and historical M2 OI045 are not retrospectively passed.
- Final local images/wheel/threehealthyservices/network-none M2/M3/M4/M6smokes and audits passed. TestCompose services and dedicatedsyntheticQdrant stopped; volumes retained. No customer ALM, remotePush/Notion, productiondeployment or destructive customer DB operation.

## Post-push remote CI — 2026-10-21

- **OI-063 / CI portability / correction locally verified, remote recheck pending:** Ubuntu amd64 run39545808983 actually failed 1/10 browser tests on screenshot ENOENT (/private/tmp); nine tests and preceding Python/frontend gates passed. Playwright-managed output path correction passed all10 locally (8.2s), independent bounded QA PASS. No test skipped/weakened. Downstream remote Docker gates remain NOT VERIFIED until corrected CI finishes. See M6/MAIN_TDD.md.
- User explicitly prioritizes CI first, then downloading/running the code on an actual Linux environment before actual ALM/model verification. Linux host access and actual ALM/model targets have not been supplied. Linux procedure: docs/LINUX_VALIDATION.ko.md. Existing model, production-scale and deployment limits remain open.

## Remote CI corrected Green — 2026-10-21

- **OI-063 / RESOLVED within tested Ubuntu24.04 amd64 scope:** run39547347678 at531ff5d SUCCESS,506Python/28frontend/10Chromium, audits0, generatedcontracts unchanged,3healthyservices andM2..M6network-none smokesPASS. Initial remoteFAIL retained above. See M6/REMOTE_CI_REPORT.md.
- OI-030 remoteCI/amd64 sub-scope now verified; user Linux host, Windows and image OS vulnerability scan remain NOT VERIFIED. Runner warned about action Node20 runtime deprecation and ubuntu-latest migration; maintenance remains pending, no failure of this run.
- Priority2 actual user Linux host download/run remains NOT VERIFIED until performed. The prepared Linux guide was independently checked; fixed-project volume reuse clarified. Actual ALM/model testing follows that environment verification per user direction.

## 사내 HTTP 실행 준비 보완

- 사용자가 HTTPS미적용 사내 운영 및 잔여실행준비 구현을 승인했다. ADR003/INTRANET/PLAN에따라 explicitHTTP,영속sameorigin서버,공유envCompose,진단·모델교정 도구를추가했다. HTTP에서도Origin/CSRF/ACL을유지한다.
- OI-064 / Ollama 응답형식호환 / RESOLVED in synthetic tests: 공식tags의 rawdigest/baredefaultname를기존엄격비교가거부했다. 실제Red후동등표현만정규화, 잘못된태그/해시/모호한중복은거부. MODEL_TDD와신규19identitycases참조. 실제모델검증은NOT VERIFIED유지.
- 전체558Python/28frontend/11Chromium, 합성HTTPComposebuild/boot/재시작로그인, 독립QA52target+8assertionsPASS. 보고서 docs/milestones/INTRANET/TEST_REPORT.md. 실제사용자Linux/ALM/Ollama/업무100k/운영복구/OS스캔은별도실행전NOT VERIFIED.
- OI-065 / 실서버 Codebeamer gzip 응답 probe 실패 / RESOLVED: 실제 Codebeamer(`/cb/api/v3/projects`)가 `Content-Encoding: gzip`으로 응답하면 `ALMHttpClient.request`가 이미 해제된 본문을 원본 `Content-Encoding`/`Content-Length` 헤더와 함께 `httpx.Response`로 다시 감싸 `DecodingError`(incorrect header check)가 매 시도 발생했고, 이를 재시도 대상 `httpx.HTTPError`로 처리해 `RETRY_EXHAUSTED`(약 33초)와 20회 누적 후 영구 `CIRCUIT_OPEN`, 브라우저 503이 나타났다. 서버·네트워크·자격증명 문제가 아니었다. `test_gzip_response_is_decoded_once` Red 후 두 헤더를 제거해 수정. 사용자 실서버에서 probe 성공과 프로젝트 목록 조회를 보고받았다(프로젝트 탐색 이후·수집·모델 연동은 NOT VERIFIED). 별도 후속: OPEN 차단기를 자동/관리자 초기화할 방법이 없어 수동 DB 갱신이 필요했고, 삼켜진 전송 예외 종류를 오류 코드에 남기지 않아 진단이 어려웠다.
- OI-066 / Codebeamer 기본 URL 문서 / RESOLVED: 문서가 기본 URL을 `/cb`까지만 안내해 `/cb/v3/projects`로 `NOT_FOUND`가 날 수 있었다. 커넥터가 `/v3/...`를 붙이므로 `…/cb/api`(`/v3` 제외)로 정정. 실제 경로는 서버마다 확인.
