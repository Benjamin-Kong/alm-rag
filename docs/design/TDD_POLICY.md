# TDD / Test-First Development Policy (v0.2 Draft)

## 1. 기본 규칙
Codex Developer Agent는 새로운 비즈니스 로직/결함 재현 시 **Red → Green → Refactor** 사이클을 우선 적용한다. 즉, 요구사항(SRS ID)에 연결된 실패하는 자동 테스트를 먼저 작성하고 실패 원인을 확인(Red), 최소한의 구현으로 통과(Green)시킨 뒤 Refactor한다. QA Agent는 독립 Review이며 구현 소스코드를 직접 수정하지 않는다.

## 2. 구현 단위 및 증거
- **Unit-first**: `AlmConnector` 어댑터 정규화, Credential mask, Chunk boundary/offset, Table, error classification, Retry scheduler, Job state machine 등 순수 로직에 Red/Green Test를 먼저 만든다.
- **Contract-test-first**: CB/Polarion fixture(Pagination/Fields/429/403/종류별 옵션)를 생성하고 Collector와 UI API를 구현한다.
- **Integration**: 실제 SQLite·Qdrant를 Test Compose에서 실행하고 외부 ALM/Ollama는 기본 Stub/Mock로 재현. Embedding Actual은 별도 optional Env Test.
- **E2E**: Playwright를 사용해 종류 선택 → Scope 탐색 → 설정 저장 → Sync/Replay → 검색 복원을 검증한다.
- TDD 증거: Commit/PR에 SRS/TEST ID, 실패 테스트 명령과 원인, 성공 명령/결과, 변경 범위, Refactor/Regression를 기록한다.

## 3. Quality Gate
- 테스트를 먼저 실행한 기록이 없는 신규 구현은 Code Review에서 TDD_NOT_EVIDENCED로 표시하며 근거/정당한 예외가 필요하다. 기계적 로그 꾸미기 금지.
- Config/Docs-only 변경은 테스트를 보강하거나 문서 검증 규칙으로 대체할 수 있으나 예외를 반드시 명시한다.
- Unit+Integration+Mock E2E 범위와 회귀 테스트를 진행하고 CI 실패 상태에서는 Milestone 승인 후보로 제출하지 않는다.
- SRS/SAD를 변경해야 하는 구현은 자동 수정 횟수와 관계없이 Human Gate 승인 요청.

## 4. QA 체크리스트
- 신규 구현 전에 실패 테스트가 존재했는가? 요구사항과 직접 연결되는가?
- 실제 Source Contract에 대한 False Positive 없이 실패 이유를 검증했는가?
- 성공 테스트 결과와 Refactor 후 회귀 결과가 있는가?
- 비밀정보·운영 ALM 접근 없이 재현 가능한가?
- 실패한 Item을 숨기거나 테스트를 skip/xfail로 둔갑시키지 않았는가?
