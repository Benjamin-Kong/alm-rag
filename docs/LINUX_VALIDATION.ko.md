# Linux 다운로드·구동 검증

실제 업무용 사내 HTTP 설치는 [사내 Linux 안내](INTRANET_LINUX.ko.md)를 사용하세요. 아래 절차의 임시 HTTPS 데모와 구분합니다.

접속 후 화면 사용법은 [한국어 웹 UI 사용 설명서](WEB_UI_GUIDE.ko.md)를 참고하세요.

사용자 지정 2순위: 실제 Linux에서 코드를 내려받아 실행하고 결과를 기록합니다. CI의 Ubuntu 검증과 사용자 Linux 서버 검증은 별도로 기록합니다. 실제 ALM·Ollama 접속은 해당 테스트 환경과 읽기 전용 범위를 정한 후 진행합니다.

## 준비와 다운로드

Git, Python 3.12, uv 0.9.18, Node.js 22/npm, Docker/Compose가 준비된 Linux 테스트 계정을 사용합니다. 비공개 저장소 인증은 해당 계정의 Git 자격증명 도구로 수행하며 토큰을 URL이나 명령에 넣지 않습니다. 다음 명령은 새 작업 디렉터리에서 실행합니다.

```sh
git clone --branch codex/m6-quality https://github.com/Benjamin-Kong/alm-rag.git
cd alm-rag
git rev-parse HEAD
git status --short
uname -sm
python3.12 --version
node --version
uv --version
docker compose version
uv sync --frozen --python 3.12
npm --prefix frontend ci
npm --prefix frontend run build
uv run python tools/validate_baseline.py
uv run python tools/validate_release.py
```

기록 대상은 OS/CPU, 커밋 SHA, 도구 버전, 명령별 종료 코드와 요약입니다. 정적 검사 PASS는 애플리케이션 실행 PASS를 뜻하지 않습니다. M2의 OI-045 증거 예외도 유지됩니다.

## 임시 HTTPS 데모와 브라우저 검증

```sh
uv run python tools/native_e2e_server.py
```

서버의 loopback에만 바인딩합니다. Linux GUI에서 `https://127.0.0.1:19443/`에 접속하거나, 서버 접속용 PC에서 별도 SSH 터널을 사용합니다.

```sh
# 아래 계정/호스트를 실제 승인된 테스트 서버로 바꿉니다.
ssh -N -L 19443:127.0.0.1:19443 <user>@<linux-host>
```

PC 브라우저에서 같은 HTTPS 주소로 접속합니다. 임시 자체 서명 인증서 경고를 확인하고, `synthetic-admin` / `synthetic browser password`로 관리자 세션에 연결합니다. 프로젝트 표시 → 무결성 작업 → 보고서 조회 → 로그아웃을 확인합니다. 합성 데이터·임시 DB만 사용하며 종료하면 정리됩니다. 실제 운영 서버로 공개하지 마세요.

자동 검증은 데모를 Ctrl+C로 종료한 뒤 실행합니다. Linux 브라우저 라이브러리 설치 과정에서 시스템 패키지 권한이 필요할 수 있습니다.

```sh
cd frontend
npx playwright install --with-deps chromium
npm run test:e2e
cd ..
```

현재 예상 테스트 수는 11개(9개 mock API + 1개 실제 임시 HTTPS/API/worker + 1개 명시적 HTTP/API/worker)입니다. 4173·19443·19444 포트가 비어 있어야 합니다. 테스트가 통과한 경우에만 PASS로 기록합니다. 실패 증거는 `frontend/test-results/`에 생성됩니다.

## 영속 컨테이너 구동

전용 테스트 프로젝트 이름을 사용합니다. 아래 이름을 처음 사용할 때만 새 볼륨이 생성되며, 재실행하면 기존 테스트 볼륨을 재사용합니다. 완전히 분리된 실행이 필요하면 사용한 적 없는 프로젝트 이름으로 모든 명령의 `-p` 값을 바꾸세요.

```sh
docker compose -p almrag-linux-check -f deploy/compose.yaml build
docker compose -p almrag-linux-check -f deploy/compose.yaml up -d --wait --wait-timeout 90
docker compose -p almrag-linux-check -f deploy/compose.yaml ps
curl --fail http://127.0.0.1:8000/api/v1/healthz
curl --fail http://127.0.0.1:8080/api/v1/healthz
docker compose -p almrag-linux-check -f deploy/compose.yaml stop
```

3개 서비스의 healthy 상태와 두 health 응답을 확인합니다. `stop`은 데이터를 보존합니다. HTTP 8080은 health/UI 확인용이며 Secure 관리자 로그인에는 별도 HTTPS 프록시가 필요합니다. 영속 관리자 생성·Native 실행은 [실행 안내](GETTING_STARTED.ko.md)를 따릅니다. Linux의 기본 `host.docker.internal` 해석은 환경에 따라 다르므로 실제 외부 모델/Qdrant 연결 전에 별도 주소 설정이 필요합니다. 기본 live 연결은 비활성입니다.

## 결과 기록

| 항목 | 최초 상태 | 기록할 증거 |
|---|---|---|
| 대상 Linux 다운로드/설치 | NOT VERIFIED | OS/CPU, SHA, lock 설치 결과 |
| 정적 문서 검사 | NOT VERIFIED | 실제 출력, M2 예외 구분 |
| HTTPS 로그인·CSRF·worker·로그아웃 | NOT VERIFIED | 실제 수동 또는 자동 브라우저 결과 |
| 영속 컨테이너 build/boot | NOT VERIFIED | 이미지 ID, healthy, 두 health 응답 |
| 실제 ALM·모델 연동 | NOT VERIFIED | 승인된 대상·범위·프로필, 합성 증거와 분리 |

고객 데이터·DB·개인키·인증 값·원문 로그는 Git에 올리지 않습니다. 오류는 비밀 값과 고객 텍스트를 제거한 요약으로 기록합니다. 이 절차 문서를 작성한 것 자체는 대상 Linux 실행 증거가 아닙니다.
