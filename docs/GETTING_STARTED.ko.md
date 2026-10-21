# ALM RAG 실행 안내

**사내 HTTP로 실제 업무 검증을 시작할 때는 [사내 Linux 설치·연동 안내](INTRANET_LINUX.ko.md)를 먼저 사용하세요.** 아래 임시 HTTPS 데모와 기본 Compose는 기존 기본 실행 방식입니다.

브라우저 화면과 입력 항목은 [한국어 웹 UI 사용 설명서](WEB_UI_GUIDE.ko.md)를 참고하세요.

현재 실행 기준은 M6입니다. 실제 Linux에서 다운로드·구동할 때는 [Linux 검증 절차](LINUX_VALIDATION.ko.md)를 사용하세요. 상세 운영 절차는 [M6 Runbook](milestones/M6/RUNBOOK.md), 검증 범위는 [검증 보고서](milestones/M6/TEST_REPORT.md), 플랫폼별 확인 결과는 [Portability](milestones/M6/PORTABILITY.md)를 참고하세요.

## 1. 준비

- Python 3.12, uv, Node.js 22/npm이 필요합니다.
- 컨테이너 모드는 Docker와 Compose가 필요합니다.
- 이 개발 PC에서는 `.venv/bin/python`과 `/opt/homebrew/opt/node@22/bin`을 사용합니다. 시스템 Python 3.9와 기본 Node 25는 검증 환경으로 사용하지 않습니다.

새로 가져오는 경우:

```sh
git clone --branch codex/m6-quality https://github.com/Benjamin-Kong/alm-rag.git
cd alm-rag
```

저장소 루트에서 설치·빌드합니다. macOS의 해당 Node 경로는 이 개발 PC에만 해당하므로 다른 환경에서는 Node 22의 설치 경로를 사용하세요.

```sh
# 이 개발 PC에서만 필요
export PATH="/opt/homebrew/opt/node@22/bin:$PATH"

uv sync --frozen
npm --prefix frontend ci
npm --prefix frontend run build
```

`.env.example`은 지원되는 설정의 예시입니다. 앱은 이 파일을 자동으로 읽지 않으므로 필요한 값을 명시적으로 export하거나 컨테이너 환경에 전달해야 합니다. 실제 비밀 값은 저장소에 넣지 않습니다.

## 2. 화면·로그인 흐름을 바로 확인하는 로컬 데모

기존에 테스트한 임시 HTTPS 실행 도구입니다. **합성 프로젝트와 임시 DB만 사용하며 실제 ALM·모델에 연결하지 않습니다.** 일반 운영 실행과 구분해서 사용하세요.

```sh
.venv/bin/python tools/native_e2e_server.py
```

- 접속: `https://127.0.0.1:19443/`
- `관리자 세션으로 연결`을 선택합니다.
- 데모 전용 이름: `synthetic-admin`
- 데모 전용 비밀번호: `synthetic browser password`
- 자체 서명된 임시 인증서를 사용하므로 브라우저에서 인증서 경고가 나올 수 있습니다. OS 인증서 저장소는 변경하지 않습니다.
- 관리자 로그인, 프로젝트 표시, 무결성 작업과 보고서 조회를 확인할 수 있습니다. 실제 검색에는 별도로 검증된 모델·인덱스가 필요합니다.
- `Ctrl+C`로 종료합니다. 임시 데이터와 인증서는 정리되며 기존 DB를 열거나 변경하지 않습니다. 운영 데이터를 보관하는 실행 방식이 아닙니다.

## 3. 데이터를 보존하는 Docker Compose 실행

일반 Docker 환경에서는 다음 명령을 사용합니다.

```sh
docker compose -p almrag-dev -f deploy/compose.yaml build
docker compose -p almrag-dev -f deploy/compose.yaml up -d --wait --wait-timeout 90
```

이 개발 PC의 Colima/독립 Compose 조합에서는 대신 다음 명령을 사용합니다. Colima의 `alm-rag` 프로필이 실행 중이어야 합니다.

```sh
DOCKER_CONTEXT=colima-alm-rag docker-compose -p almrag-dev -f deploy/compose.yaml build
DOCKER_CONTEXT=colima-alm-rag docker-compose -p almrag-dev -f deploy/compose.yaml up -d --wait --wait-timeout 90
```

기본 주소:

| 용도 | 주소 |
|---|---|
| 프론트엔드 HTTP | `http://127.0.0.1:8080/` |
| API liveness | `http://127.0.0.1:8000/api/v1/healthz` |
| 프론트엔드 경유 API | `http://127.0.0.1:8080/api/v1/healthz` |

최초 관리자 생성은 **컨테이너와 동일한 DB 볼륨에서** 실행합니다. 비밀번호는 터미널에서 숨김 입력하며 16자 이상이어야 합니다.

```sh
docker compose -p almrag-dev -f deploy/compose.yaml exec api python -m almrag.cli bootstrap-admin
# 이 개발 PC에서는 위 명령 대신:
# DOCKER_CONTEXT=colima-alm-rag docker-compose -p almrag-dev -f deploy/compose.yaml exec api python -m almrag.cli bootstrap-admin
```

**기본 모드의 관리자 브라우저 로그인에는 HTTPS가 필요합니다.** 명시적으로 선택한 사내 HTTP 모드는 `ALMRAG_INTRANET_HTTP_ENABLED=true`와 정확한 HTTP Origin을 사용하는 [별도 사내 구성](INTRANET_LINUX.ko.md)을 따릅니다. HTTP 8080 주소만으로는 Secure 세션 로그인이 성립하지 않습니다. HTTPS 리버스 프록시가 프론트엔드 8080으로 연결되도록 준비하고, 실제 브라우저 Origin과 API의 `ALMRAG_ALLOWED_ORIGIN`을 일치시켜야 합니다. 기본 Origin은 `https://localhost:8443`입니다. TLS 인증서·프록시의 운영 구성은 별도 환경 설정 사항이며 이 저장소의 기본 Compose에 포함되어 있지 않습니다. CSRF·Secure 쿠키 설정은 그대로 유지합니다.

종료는 `stop`을 사용하면 볼륨이 보존됩니다.

```sh
docker compose -p almrag-dev -f deploy/compose.yaml stop
# 이 개발 PC에서는:
# DOCKER_CONTEXT=colima-alm-rag docker-compose -p almrag-dev -f deploy/compose.yaml stop
```

기존 데이터가 있는 볼륨에 `down -v`를 사용하지 마세요.

## 4. Native API·Worker 실행

루트 디렉터리에서:

```sh
export ALMRAG_DATABASE_PATH="$PWD/data/alm.sqlite"
export ALMRAG_ALLOWED_ORIGIN="https://localhost:8443"

.venv/bin/python -m almrag.cli migrate
.venv/bin/python -m almrag.cli bootstrap-admin
.venv/bin/python -m almrag.api
```

다른 터미널에서 동일한 DB 경로를 지정한 뒤 Worker를 실행합니다.

```sh
export ALMRAG_DATABASE_PATH="$PWD/data/alm.sqlite"
.venv/bin/python -m almrag.worker
```

API는 8000 포트에서 실행됩니다. Native에서 UI까지 함께 제공하려면 API 명령 대신 `uv run python -m almrag.server --host 0.0.0.0 --port 8000`을 사용할 수 있습니다. 먼저 frontend를 빌드하고 영속 DB·일치하는 Origin·사내 HTTP 명시 설정을 적용해야 합니다. 이 진입점에는 데모 계정이 없으며 최초 관리자를 직접 생성합니다. Worker는 별도로 실행합니다.

별도 웹 서버를 선택하는 경우: 빌드된 `frontend/dist`와 `/api/v1` 프록시를 같은 HTTPS Origin으로 제공하는 웹 서버가 별도로 필요합니다. `npm run dev`만 실행하면 API 프록시까지 자동 구성되는 것은 아닙니다. Native API·Worker와 Compose API·Worker를 같은 작업 DB에 중복 실행하지 마세요.

## 5. 실제 ALM·모델을 사용하기 전

기본값은 다음과 같습니다.

```sh
ALMRAG_LIVE_ALM_ENABLED=false
ALMRAG_LIVE_MODEL_ENABLED=false
ALMRAG_LIVE_VECTOR_ENABLED=false
ALMRAG_NOTION_SUMMARY_ENABLED=false
```

실제 연결에는 허용된 ALM Origin·자격증명 참조, 검증된 모델/토크나이저 프로필, Qdrant 주소·인증·TLS 설정이 필요합니다. API와 Worker 양쪽에 필요한 설정을 전달해야 하며 Compose는 임의의 호스트 환경변수를 모두 전달하지 않습니다. 자세한 설정은 `.env.example`과 M3~M6 Runbook을 확인하세요.

실제 서버에서 소스 유형 선택 → 서버 검증 → 프로젝트/Tracker 또는 Work Item Type 선택 → 필드·제한 설정 → Preflight → SYNC 순서로 진행합니다. 현재 저장소의 검증 결과가 실제 ALM/Ollama 호환성이나 운영 10만 Item 처리의 검증을 대신하지 않습니다.
