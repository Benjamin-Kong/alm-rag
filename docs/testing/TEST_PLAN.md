# Quality, Test and Search Evaluation Plan (Draft)

## Verification levels
- Unit: field normalization/type round-trip, HTML DOM, rowspan/colspan, fallback, chunk identity/hash, model fingerprint, RRF grouping, prefix policy.
- Integration: SQLite migrations/WAL, Qdrant upsert/query, keyword engine, Ollama stub+actual optional, UI to FastAPI, crash-restart worker.
- Mock E2E: paginated fake CB/Polarion APIs, 429/403/5xx cases, custom fields, attachments/checksum, item revisions/deletion/scope, backup/export/import.
- Actual ALM: optional, permission-limited read-only compatibility probe. `NOT VERIFIED` until real servers and credentials supplied.
- Security: forbidden project filter, API key revocation, log redaction, XSS-safe rich HTML, SSRF protections for configured endpoints, unauthorized file paths.
- Consistency: fail between SQLite revision commit and Qdrant upsert; fail between Qdrant staging and activation; service restart; concurrent queries during publication; cancellation.
- Runtime portability: Windows/macOS/Linux; Docker/Native.

## Test traceability
`docs/testing/TEST_CASES.md` defines TEST-001~043 at specification level; TEST-044~059 scenarios appear below. `docs/requirements/TRACEABILITY.csv` maps each `SRS-xxx` to `TEST-xxx`; test IDs are reserved names, NOT implemented tests. Each test must produce observed PASS/FAIL/NOT VERIFIED; no fabricated results.

M1 supplement: applicable foundation subcases are now implemented in tests/ and frontend/src/*.test.*; execution evidence and code/test mapping are in docs/milestones/M1/TEST_REPORT.md and M1_TRACEABILITY.csv. Product-level TEST IDs remain only partially verified where their primary behavior belongs to later milestones. CI definition covers the current foundation; remote CI has not run.

## Golden retrieval dataset
Project UID + query + relevant item UID(s), ~20–50 manually verified queries initially. Record Precision@K/Recall@K/MRR. Compare Vector-only, Keyword-only and Hybrid with same filters and item-level metric denominator. Include `SOME/IP-SD`, `30490`, `0x...`, Korean semantic paraphrase and table row semantics.

## Gates
- Applicable unit+integration+mock E2E all PASS; missing environment-bound tests marked NOT VERIFIED with limitation.
- No unresolved Critical/Major problems in scoped functionality; code quality, doc parity, traceability checked.
- Failure: auto fix/QA loop max 3 attempts; escalate immediately if data damage, sensitive exposure or approved architecture changes.
- M6: benchmark 100,000 Items goal, P95≤3s warm single request, top_k=10, lightweight payload; report hardware and sample sizes.

## v0.2 신규 테스트 명세
| Test ID | Given/When/Then 검증 | Source |
|---|---|---|
| TEST-044 | Codebeamer Wizard 에서 Project→Tracker ID 선택·저장·sync | SRS-044 |
| TEST-045 | 접속/인증/Version 탐색 실패 시 저장·시작 차단 및 오류 설명 | SRS-045 |
| TEST-046 | Polarion `workitem-type` enumeration으로 Type ID 선택, Tracker ID 오용 금지 | SRS-046 |
| TEST-047 | Preflight 시 scope, 인증, 예상 건수, API 능력 검증 | SRS-047 |
| TEST-048 | 큰 문장/표/필드가 max tokens 초과 없이 분할되고 silent truncation 없음 | SRS-048 |
| TEST-049 | 15k tokens Item 원본과 모든 Field/표 셀을 Item 전체복원으로 회수 | SRS-049 |
| TEST-050 | rowspan/colspan 표 행 그룹/셀 분해/헤더 대응 보존 | SRS-050 |
| TEST-051 | Linux API/Worker/Frontend Docker build/boot/healthcheck 및 볼륨 | SRS-051 |
| TEST-052 | Python/Node lock-file pinned, CI dependency audit, Native install | SRS-052 |
| TEST-053 | 2 RPS+burst2 설정에서 API/파일/HTML 호출 합산 rate 준수 | SRS-053 |
| TEST-054 | 429 Retry-After:15 대기, 5xx 지수 backoff, 401/403 무재시도 | SRS-054 |
| TEST-055 | 100개 중 3개 실패 시 정상 97개 계속 처리, 검색 active 보존 | SRS-055 |
| TEST-056 | 특정 Item Stage 재시도 성공, revision/vector 중복 없음 | SRS-056 |
| TEST-057 | Worker Kill/Restart 및 AUTH 실패에서 고유 correlation 로그·원인 마스킹 | SRS-057 |
| TEST-058 | 실패하는 첫 테스트와 구현 후 성공 테스트가 SRS ID에 연결되어 있음 | SRS-058 |
| TEST-059 | UI/429/Chunk/Docker/TDD 의무 Gate가 누락 없이 CI에서 판정 | SRS-059 |

기존 Q40/B안 정책과 일치: Unit + Integration + Mock E2E 자동화를 기본 필수화하고 실제 ALM 접속은 환경 제공 시 추가 검증한다. Runtime 이미지 미빌드/미시험 상태는 PASS로 표시하지 않는다. 엄격한 일률 커버리지 수치 미강제(Q46 B).
