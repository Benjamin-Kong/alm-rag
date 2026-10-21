# 사내 HTTP 실행 준비 검증 보고서

사용자가 HTTPS 미적용 사내 사용 및 남은 실행·연동 준비 구현을 명시적으로 승인했다. 이 결과는 개발 환경의 합성 검증이며 실제 업무 서버 접속 결과가 아니다.

## 구현

- `ALMRAG_INTRANET_HTTP_ENABLED=true` +정확한HTTP Origin일 때만 비Secure 쿠키를 사용한다. 기본 HTTPS Secure·HttpOnly·SameSite·CSRF·Origin·프로젝트 ACL은 유지한다. CLI도 같은 HTTP opt-in/Origin조건을 따른다.
- `python -m almrag.server`는 영속DB의 실제 UI/API 진입점이며 데모 계정·임시DB를 만들지 않는다. Worker는 독립 실행한다.
- `deploy/compose.intranet.yaml`은 API/Worker 동일 privateenv, 영속SQLite/첨부, 읽기전용 config, restart정책, 인증된 선택적Qdrant를 제공한다. 실제설정은 `deploy/intranet.env.example`, `docs/INTRANET_LINUX.ko.md`를 따른다.
- `python -m almrag.doctor`는 기본 오프라인검사, 명시적옵션으로서비스/ALM 읽기probe를 제공한다. 모델준비도구는 실제tokenizer해시/설정 검사 및 명시적Ollama교정 후 프로필을 원자적으로게시한다.
- Ollama 공식tags의 raw64hex/prefixed digest, bare/defaultlatest 이름 형식만 동등비교한다. 다른태그/해시/중복/토큰수불일치는거부한다.

## 실제 실행 결과

| 검사 | 결과 | 근거 |
|---|---|---|
| 신규·관련 Python | PASS | root71targetPASS3.40s |
| 전체 Python +전용합성Qdrant | PASS | 558passed77.69s, SKIP없음 |
| Frontend | PASS | 28tests/9files1.35s, TypeScript/Vitebuild712ms |
| 실제 Chromium | PASS | 11passed9.6s:9mockAPI +1HTTPS +1HTTP 실제session/CSRF/worker/report/logout |
| 독립 QA | PASS | 52targetPASS1.75s +8합성HTTP assertions; 확인범위Critical/Major없음 |
| 사내 Compose 이미지build/boot | PASS | Linuxarm64 API f1509421f36f/frontend e4a55374c131; API/worker/frontend/Qdrant4Healthy |
| 실제 합성HTTP Compose접속 | PASS | loopback18080 health/UI/인증/API보호/HttpOnly/CSRF/Origin/logout |
| 재시작 보존 | PASS | 같은 합성볼륨에서 API/workerrestart뒤 기존계정HTTP로그인·로그아웃 재검증PASS |
| 컨테이너내doctor | PASS +NOT VERIFIED | runtime/storage/SQLite3PASS,0FAIL; profile/ALM/Ollama/vector연결4NV |
| 패키징 | PASS | wheel/sdistbuild, freshofflinewheelinstall, schema1..9중복마이그레이션; server/doctor/model_setup wheel포함 |
| 문서/정적게이트 | PASS with exception | baseline/release문서검사, 링크31개0누락, diffcheck; M2 OI045역사적예외유지 |
| 신규 원격CI | NOT VERIFIED at report writing | 전용합성HTTP Compose기동·재시작·doctor게이트추가, Push후실행결과별도확인 |
| 실제 업무Linux/ALM/Ollama | NOT VERIFIED | 대상서버·실제자격증명·모델아티팩트 사용하지않음 |

원래HTTP/server/CLI/model/doctor Reds와 수정내역은 HTTP_TDD.md, MODEL_TDD.md, DEPLOY_TDD.md에 보존한다. 독립QA는 구현을수정하지않았고 전체suite/browser/container실행은root증거다. 로컬 합성 Qdrant는 실제 업무벡터저장소 검증을 대신하지 않는다. 마지막 추가Qdrant인증접속 확인명령은 도중 중단되어 실행성공으로계산하지않는다.

## 실제 서버에서 남는 검증

Linux설치/HTTP접속/영속성, 실제Codebeamer·Polarion읽기계정/CA/버전/프로젝트/Tracker·Type/첨부수집, 실제Ollama·tokenizer교정/벡터차원/검색품질, 실제Qdrant연결, 작은프로젝트수집→PROCESS→EMBED→INDEX→검색, 권한거부/무결성/실패재처리, 업무질문평가와백업·격리복구를 INTRANET_LINUX.ko.md 순서로 확인한다. 실제100k전체처리량·OS이미지취약점검사·Windows·실제Notion전송도미검증이며 구현완료를근거로PASS로올리지않는다. 외부SQL DB 지원은추가하지않았고 원본DB는로컬SQLite다.
