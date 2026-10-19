# ALM API Throttling, Retry 및 서버 보호 정책 (v0.2 Draft)

## 1. 범위
서버별·인증 프로필별 공통 요청 스케줄러를 두어 **GET 프로젝트 탐색/페이지 목록/Item 상세/첨부 다운로드/Content 렌더링** 모두 합산해 속도를 제어한다. 동시성 제한과 초당 RPS는 서로 다른 정책이다. 백엔드/Worker가 여러 개여도 같은 서버에 대한 속도 제한이 일관되도록 서버별 중앙 예산이 필요하다. 초기 한 Worker 정책(Q26)에서 SQLite 기반 공유 토큰/락 고려.

## 2. 정책 초기값 (운영자가 변경 가능, 서버 실제 한도 아님)
| 설정 | 초깃값 | 범위 및 의미 |
|---|---|---|
| `requests_per_second` | 2.0 | ALM 서버당 평균 토큰 버킷 충전율. 실서버 벤치마크 후 조절 |
| `burst` | 2 | 순간 최대 burst 토큰 |
| `max_inflight` | 2 | 동시 HTTP 요청 수 |
| `min_interval_ms` | 200 | 연속 요청 간 최소 간격(서버별) |
| `request_timeout_seconds` | 30 | 기본 호출 Timeout(파일 Download는 별도 stream timeout) |
| `max_attempts` | 5 | 원 시도 포함 총 시도 횟수 |
| `backoff_base_seconds` | 2 | exponential backoff 기본값 |
| `backoff_max_seconds` | 120 | 오류별 대기 상한(서버 Retry-After 처리 정책 별도) |
| `circuit_breaker_window` | 20 | 연속/빈번한 일시 장애 감지 기준의 최근 표본 |

## 3. 분류
- 429: `Retry-After` delta-seconds/HTTP-date가 유효하면 그 시점 **이전에는 호출하지 않음**. 모든 같은 서버 작업에 공유 pause. 없으면 지수 backoff+jitter. 제한 반복 시 서버 프로필 PAUSED.
- 500/502/503/504, connection reset, timeout: 멱등 읽기 요청에 한해 제한적 재시도. Retry-After 존재 시 존중. 지수 backoff+jitter.
- 401: AUTH_FAILED, 전역 해당 Credentials의 Job을 BLOCKED, 자격증명 교체 필요. 403: PERMISSION_DENIED, 해당 scope/Item만 격리하되 구조적 권한 변경이면 Job PAUSED; 무조건 재시도하지 않음.
- 400/422: INVALID_REQUEST/SCHEMA_MISMATCH로 영구 오류, Mock fixture 및 connector version 문제 확인. 404: Item 삭제의 충분조건이 아님; 재조회, 권한/Scope 변화를 확인하고 DELETED/OUT_OF_SCOPE/UNKNOWN 상태 구분.
- 읽기 전용 `POST wiki2html`은 대상 API가 실제 서버를 수정하지 않는다는 계약/테스트 검증 시에만 retry 가능. 일반 POST/PUT/DELETE는 ALM Collector 금지.

## 4. 영속 상태·UI
- ServerProfile마다 정책값, 관측된 429, 유효 RPS, retry_count, next_eligible_at, circuit_state 저장.
- 모든 Retry를 기록하되 Secret/원본문자/인증 헤더/쿼리 본문 로깅 금지.
- 운영자는 ServerProfile Rate Limit을 실시간 조절할 수 있으며 적용 대상은 신규/대기 요청이다.
- 서버 Pause와 개별 Item 실패를 혼동하지 않는다. Global API 보호 정책 위반 위험이면 신속하게 전체 서버별 요청을 멈춘다.

## 5. Given/When/Then 검증
- Given 서버 2 RPS, burst2; When 프로젝트/첨부/렌더 혼합 요청; Then 모두 같은 버킷을 사용하고 초과하지 않는다.
- Given 429 Retry-After:15; When 재시도 예약; Then 동일 서버 어느 요청도 대기 만료 전 실행되지 않는다.
- Given 403 permission; When 재시도; Then 429/5xx와 달리 자동 재시도하지 않고 명시적 분류/격리한다.
- Given Worker restart; When Job 재개; Then 영속 pause/backoff/checkpoint를 복원하여 과다 요청하지 않는다.
