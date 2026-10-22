# 사내 HTTP Linux 설치·실서버 검증 안내

사용자는 2026-10-21 사내망에서 HTTPS 없이 사용하는 방식을 명시적으로 선택했다.
이 문서는 종료하면 사라지는 `native_e2e_server.py` 데모 대신 **영속 SQLite·API·Worker·웹 UI**를 설치한다.
HTTP 예외는 `ALMRAG_INTRANET_HTTP_ENABLED=true`와 정확한 접속 Origin을 함께 설정해야 활성화된다.
관리자 비밀번호·세션·업무 데이터는 이 구간에서 HTTP로 전송되므로 사내에서 허용된 접근망에만 포트를 개방한다.
인증·권한·CSRF 검사는 계속 적용되며 ALM 서버의 HTTPS 인증서 검증은 끄지 않는다.

## 1. 준비 사항

- 기준: Ubuntu 24.04 x86_64, Bash, Git, Docker Engine 및 Compose v2 플러그인.
- 초기 이미지 빌드에는 Python/Node 패키지 및 컨테이너 레지스트리에 접근할 수 있어야 한다.
- 실제 업무 용량은 첨부·원본·정규화·벡터 크기에 따라 달라진다. 충분한 디스크를 준비하고 소규모 프로젝트부터 측정한다.
- 사내 Codebeamer/Polarion 주소와 읽기 전용 서비스 계정, Ollama 임베딩 모델과 대응 토크나이저, Qdrant 주소를 준비한다.
- 별도 SQL 서버는 지원하지 않는다. 앱의 원본/상태 저장소는 **단일 서버 로컬 SQLite**이며 벡터 저장소만 Qdrant다. SQLite 볼륨을 NFS에 두거나 여러 서버에서 공유하지 않는다.

Docker 설치는 [Ubuntu 공식 절차](https://docs.docker.com/engine/install/ubuntu/)를 따른다.
설치 후 아래 명령으로 확인한다. Docker 권한을 부여하지 않은 계정은 명령 앞에 `sudo`를 사용한다.

```bash
sudo apt update
sudo apt install -y git curl ca-certificates python3
sudo systemctl enable --now docker
sudo docker version
sudo docker compose version
```

저장소 접근은 사내 GitHub 정책에 맞는 HTTPS 자격증명 또는 SSH 키를 사용한다. 비밀번호·토큰을 clone URL에 넣지 않는다.

```bash
mkdir -p ~/projects
cd ~/projects
git clone --branch codex/m6-quality https://github.com/Benjamin-Kong/alm-rag.git
cd alm-rag
git rev-parse HEAD
mkdir -p config
cp deploy/intranet.env.example .env.intranet
chmod 600 .env.intranet
```

`.env.intranet`은 Git 제외 대상이다. 이 파일의 내용을 공유하거나 `docker compose config`의 전체 출력(비밀번호 포함 가능)을 로그에 저장하지 않는다.
Compose에는 `--env-file .env.intranet`을 **항상** 지정한다. 앱은 임의 `.env`를 자동 로드하지 않지만 이 구성의 Compose `env_file`이 API·Worker 양쪽에 전달한다.

## 2. 실제 서버 주소와 비밀정보 설정

`.env.intranet`을 편집한다. 아래 IP는 예시이므로 실제 서버 IP 또는 DNS 이름으로 바꾼다.

```dotenv
ALMRAG_INTRANET_HTTP_ENABLED=true
ALMRAG_ALLOWED_ORIGIN=http://10.0.0.20:8080
ALMRAG_BIND_ADDRESS=0.0.0.0
ALMRAG_HTTP_PORT=8080
```

Origin은 브라우저 주소의 **scheme·host·port**와 일치해야 하며 경로·끝의 `/`를 넣지 않는다.
`localhost`, IP, DNS 이름을 섞으면 로그인/CSRF 검사가 거부할 수 있다.
방화벽에는 필요한 사내 대역에서 TCP 8080만 허용한다. API 8000과 내장 Qdrant 6333은 호스트에 직접 공개하지 않는다.

Qdrant API 키를 서버에서 생성한다. 터미널 출력이나 채팅에 붙이지 않고 비공개 파일에 추가한다.

```bash
umask 077
python3 -c 'import secrets; print("ALMRAG_QDRANT_API_KEY="+secrets.token_urlsafe(48))' >> .env.intranet
```

Basic 인증 비밀번호는 코드나 UI의 참조 칸에 넣지 않는다. Bash에서 숨김 입력 후 환경 파일에 리터럴 문자열로 기록한다.
이 방식은 `$`, `#`, 공백 등 Compose 보간에 특별한 문자가 있는 비밀번호에도 대응하도록 **작은따옴표 dotenv 값**을 생성한다.
줄바꿈과 작은따옴표가 포함된 비밀번호는 아래 방법 대신 후술한 `vault:` 저장을 사용한다.

```bash
read -r -s -p 'Codebeamer password: ' ALMRAG_CODEBEAMER_PASSWORD
echo
export ALMRAG_CODEBEAMER_PASSWORD
python3 - <<'PY'
import os
value=os.environ['ALMRAG_CODEBEAMER_PASSWORD']
if any(c in value for c in "'\r\n"):
    raise SystemExit('Use vault storage for this password character set.')
with open('.env.intranet','a') as stream:
    stream.write("\nALMRAG_CODEBEAMER_PASSWORD='"+value+"'\n")
PY
unset ALMRAG_CODEBEAMER_PASSWORD
```

API/Worker가 이미 실행 중이라면 env 파일 변경 후 `up -d --force-recreate api worker`로 다시 생성한다. 단순 `restart`는 변경된 환경을 다시 읽지 않는다.
API·Worker에 동일한 자격증명 참조와 CA/모델 파일이 있어야 한다.

## 3. 빌드·영속 기동·첫 관리자 생성

다음은 같은 서버에 인증된 Qdrant도 함께 띄운다. 기존 외부 Qdrant를 쓴다면 `--profile services`를 빼고 `.env.intranet`의 `ALMRAG_QDRANT_URL`을 실제 주소로 바꾼다.
외부 Qdrant 키는 그 서버에 설정된 실제 키와 같아야 한다.

```bash
sudo docker compose --env-file .env.intranet -p almrag-intranet \
  -f deploy/compose.intranet.yaml --profile services build
sudo docker compose --env-file .env.intranet -p almrag-intranet \
  -f deploy/compose.intranet.yaml --profile services up -d --wait --wait-timeout 120
sudo docker compose --env-file .env.intranet -p almrag-intranet \
  -f deploy/compose.intranet.yaml ps
sudo docker compose --env-file .env.intranet -p almrag-intranet \
  -f deploy/compose.intranet.yaml exec api python -m almrag.cli bootstrap-admin --username admin
```

암호는 숨김 프롬프트에서 16자 이상으로 입력한다. 첫 관리자만 생성 가능하며 데모 계정은 생성하지 않는다.
`http://실제서버주소:8080/`에서 관리자 세션 연결을 선택한다. UI 사용 순서는 [웹 UI 설명서](WEB_UI_GUIDE.ko.md)를 참조한다.
API와 UI는 프록시를 통해 같은 Origin을 사용한다. UI를 별도 Vite 개발 서버에서 실행할 필요가 없다.

SQLite·첨부·Export·백업은 Compose 프로젝트 `almrag-intranet`의 `almrag_data` 볼륨에 보존된다.
프로젝트 이름을 바꾸면 다른 볼륨이 만들어진다. **`down -v`는 보존 데이터를 삭제하므로 운영 명령으로 사용하지 않는다.**

## 4. 오프라인 환경 점검과 명시적 서비스 점검

```bash
# 네트워크 요청 없이 런타임·기존 SQLite 무결성/스키마·로컬 프로필 검사
sudo docker compose --env-file .env.intranet -p almrag-intranet \
  -f deploy/compose.intranet.yaml exec api python -m almrag.doctor

# 작업자가 실제 사용하는 환경에서도 동일하게 검사
sudo docker compose --env-file .env.intranet -p almrag-intranet \
  -f deploy/compose.intranet.yaml exec worker python -m almrag.doctor

# 명시적으로 Ollama /api/tags와 Qdrant /healthz GET 요청 허용
sudo docker compose --env-file .env.intranet -p almrag-intranet \
  -f deploy/compose.intranet.yaml exec api python -m almrag.doctor --services
```

출력은 PASS/FAIL/NOT VERIFIED와 고정 오류 코드만 포함한다. 실패가 하나라도 있으면 종료 코드 1이다.
기본 검사는 없는 DB를 만들거나 마이그레이션하지 않는다. DB의 로컬 SQLite 구조 검사는 원본-Chunk-벡터 의미적 일치 검사를 대신하지 않는다.
서비스 probe PASS는 연결 확인이며 모델 일치·임베딩·벡터 CRUD·검색 성공을 뜻하지 않는다.
`--services`는 live flag와 별도로 **명시적 읽기 요청 허용 옵션**이다.

## 5. Codebeamer / Polarion 실제 연결

먼저 `.env.intranet`에 허용할 **정확한 ALM Origin**을 등록하고 명시적으로 활성화한다.

```dotenv
ALMRAG_LIVE_ALM_ENABLED=true
ALMRAG_ALLOWED_ALM_ORIGINS=https://codebeamer.company.example,https://polarion.company.example
```

위 값은 주소 형식 예시다. 실제 사내 주소로 교체한다.
ALM이 사내 CA를 사용한다면 공개 CA 인증서 체인만 `config/company-ca.pem`에 놓고 다음처럼 설정한다.

```dotenv
ALMRAG_ALM_CA_PATH=/app/config/company-ca.pem
```

UI Codebeamer 등록 예:

| 필드 | 값 |
|---|---|
| 종류 | Codebeamer |
| Base URL | `/v3` 바로 앞까지의 REST API 기준 주소. 일반적으로 `http://실제호스트:포트/cb/api`(context root `/cb` + `/api`)이며 `/v3`는 덧붙이지 않는다. 커넥터가 `/v3/projects`를 조합하므로 `/cb`만 입력하면 `NOT_FOUND`가 날 수 있다. 실제 경로는 서버에서 확인한다. |
| 인증 | Basic |
| 사용자 이름 | 읽기 전용 Codebeamer 계정 ID |
| 자격증명 참조 | `env:ALMRAG_CODEBEAMER_PASSWORD` |
| CA 참조 | 필요한 경우 `env:ALMRAG_ALM_CA_PATH` |

Polarion은 REST v1 Bearer 인증을 사용하며 Base URL에 `/rest/v1`까지 포함한다. 예: `https://실제호스트/polarion/rest/v1`.
API·Worker 재생성 후 연결 확인 → 프로젝트 탐색 → Tracker(또는 Work Item Type) 탐색 → 작은 프로젝트 등록을 수행한다.
필드 매핑·첨부 용량·레이트 제한을 검토하고 수집 Preflight 후 수집 작업을 실행한다.
서버 Wiki renderer POST는 검증되지 않았으므로 사용하지 않는다.

등록된 인스턴스 UID를 알고 있다면 CLI에서도 같은 공유 rate-limit transport로 읽기 전용 probe를 실행할 수 있다.
ALM probe는 프로젝트 탐색 요청을 보내고 **로컬 rate-limit 상태를 기록할 수 있지만 ALM 콘텐츠는 수정하지 않는다.**

```bash
sudo docker compose --env-file .env.intranet -p almrag-intranet \
  -f deploy/compose.intranet.yaml exec api python -m almrag.doctor --alm-instance 실제인스턴스UID
```

`vault:` 사용 시 `.env.intranet`에 서버에서 생성한 Fernet `ALMRAG_MASTER_KEY`를 보관하고 컨테이너에서
`python -m almrag.cli store-secret codebeamer-password`를 실행한 뒤 UI 참조를 `vault:codebeamer-password`로 입력한다.
master key는 DB 백업과 별도로 안전하게 보관해야 하며 분실 시 저장한 비밀번호를 다시 등록해야 한다. 최초 키는 아래처럼 비공개 환경 파일에 직접 추가할 수 있다. 이미 사용 중인 키를 새 값으로 교체하면 기존 암호문을 읽을 수 없으므로 재생성하지 않는다.

```bash
umask 077
python3 -c 'import base64,os; print("ALMRAG_MASTER_KEY="+base64.urlsafe_b64encode(os.urandom(32)).decode())' >> .env.intranet
sudo docker compose --env-file .env.intranet -p almrag-intranet \
  -f deploy/compose.intranet.yaml up -d --force-recreate api worker
sudo docker compose --env-file .env.intranet -p almrag-intranet \
  -f deploy/compose.intranet.yaml exec api python -m almrag.cli store-secret codebeamer-password
```

마지막 명령에서 비밀번호를 숨김 입력한다. UI에는 `vault:codebeamer-password`를 지정한다.

## 6. Ollama·토크나이저·Qdrant 연결

Ollama가 이미 사내 서버에 있다면 그 주소를 사용한다. 새 테스트 서버에 설치하는 경우 [Ollama Linux 설치 안내](https://docs.ollama.com/linux)의 공식 설치 프로그램을 사용하고 설치 버전을 기록한다. 이 명령은 실제 서버의 운영자가 수행한다.

```bash
curl -fsSL https://ollama.com/install.sh -o /tmp/almrag-ollama-install.sh
sh /tmp/almrag-ollama-install.sh
sudo systemctl enable --now ollama
ollama --version
ollama pull embeddinggemma-2
```

모델 pull은 네트워크 다운로드이며 실제 적용한 태그와 digest를 고정해서 사용한다. 같은 모델의 tokenizer.json은 승인된 공급자에서 별도로 준비한다. 앱에서 임의로 다운로드하거나 테스트 토크나이저를 운영에 사용하지 않는다. 앱은 모델·토크나이저를 자동 다운로드하지 않는다.
Ollama가 호스트에서 실행 중이면 컨테이너에서 접근할 수 있는 수신 주소로 설정하고 컨테이너 대역만 접근을 허용한다.
Ollama의 systemd 수신 주소는 [공식 FAQ](https://docs.ollama.com/faq)의 `OLLAMA_HOST` 설정을 따른다. `sudo systemctl edit ollama.service`에서 `[Service]` 아래 `Environment="OLLAMA_HOST=0.0.0.0:11434"`를 지정한 경우 daemon-reload/restart가 필요하며, 사내 방화벽에서 앱 컨테이너/허용 대역만 접근시킨다. 사내 전용 인터페이스로 바인딩할 수도 있으며 이 경우 `.env.intranet`에 해당 인터페이스의 주소를 지정한다.

`host.docker.internal`은 Compose의 `host-gateway` 매핑이다. 호스트의 `127.0.0.1:11434`에만 바인딩된 서비스는 접근할 수 없다.
별도 사내 모델 서버면 `.env.intranet`의 `ALMRAG_OLLAMA_BASE_URL`을 그 서버 주소로 바꾼다.

모델 준비 도구를 호스트에서 실행할 때는 uv와 Python 3.12가 추가로 필요하다. Docker만으로 앱을 실행하는 경우 호스트 Node 설치는 필요하지 않다. 아래 명령은 uv를 사용자 계정에 설치한다.

```bash
curl -LsSf https://astral.sh/uv/0.9.18/install.sh -o /tmp/almrag-uv-install.sh
sh /tmp/almrag-uv-install.sh
source "$HOME/.local/bin/env"
uv python install 3.12
```

uv 설치 방식은 [공식 설치 안내](https://docs.astral.sh/uv/getting-started/installation/)를 따른다. 실제 모델 프로필 준비와 교정은 [모델 설정 안내](MODEL_SETUP.ko.md)를 따른다.
승인된 동일 모델의 tokenizer.json을 `config/tokenizer.json`에 준비하고 공급자 해시와 실제 모델 digest·dimension·최대 입력 토큰을 확인한다.
다음 명령은 값의 형식 예시이며 `<...>`를 실제 확인한 값으로 교체한다.

```bash
uv sync --frozen --python 3.12
uv run python tools/prepare_model_profile.py \
  --tokenizer config/tokenizer.json --tokenizer-sha256 '<64자리 SHA256>' \
  --digest 'sha256:<모델 digest 64자리>' --dimension 768 --max-input-tokens 1024 \
  --model '<실제 Ollama 모델 이름>' --output config/model-profile.json
```

`config` 전체가 API·Worker에 읽기 전용 `/app/config`로 마운트된다. 프로필과 tokenizer를 함께 이동해야 상대경로가 유지된다.
컨테이너는 UID 10001로 실행하므로 호스트 소유의 0600 파일을 읽을 수 없다. 공개 모델 메타데이터·토크나이저·공개 CA에 한해 다음처럼 읽기 권한을 부여한다.
개인키나 비밀번호 파일을 `config`에 넣지 않는다.

```bash
chmod 755 config
chmod 644 config/model-profile.json config/tokenizer.json
# 사내 공개 CA를 추가한 경우만 실행
# chmod 644 config/company-ca.pem
```

설정 예:

```dotenv
ALMRAG_MODEL_PROFILE_PATH=/app/config/model-profile.json
ALMRAG_LIVE_MODEL_ENABLED=true
ALMRAG_LIVE_VECTOR_ENABLED=true
ALMRAG_QDRANT_AUTH_REF=env:ALMRAG_QDRANT_API_KEY
```

모델 서버 HTTPS CA는 `ALMRAG_CA_BUNDLE=/app/config/company-ca.pem`, Bearer 참조는
`ALMRAG_OLLAMA_AUTH_REF=env:ALMRAG_OLLAMA_TOKEN`으로 설정한다. 필요한 실제 토큰은 비공개 env 파일에만 넣는다.
API·Worker를 다시 생성하고 `doctor --services`로 연결을 확인한다.
모델 검증에는 **실제 토큰 수 보정**이 필요하며 잘못된 모델·해시·차원·토크나이저·보정 결과를 우회하지 않는다.
처리 Preflight → PROCESS → EMBED → INDEX 또는 SYNC 후 검색을 실행한다.

## 7. 실사용 승인 전 수행할 실제 서버 검증

결과는 [Linux 검증 절차](LINUX_VALIDATION.ko.md)의 기록과 함께 보관하되 고객 본문·자격증명·원본 로그는 Git에 올리지 않는다.

| 순서 | 확인할 내용 | 이 문서 작성 시 상태 |
|---|---|---|
| 1 | 실서버 이미지 빌드·API/Worker/UI healthy·HTTP 관리자 로그인·로그아웃 | NOT VERIFIED |
| 2 | 관리자 생성 유지·서버 재시작 후 프로젝트·작업·원본 보존 | NOT VERIFIED |
| 3 | 실제 ALM Basic/Bearer·CA·프로젝트/종류/필드 탐색 | NOT VERIFIED |
| 4 | 소규모 읽기 전용 수집·첨부·표·긴 Item·실패 목록/재처리 | NOT VERIFIED |
| 5 | 실제 Ollama 식별/보정/임베딩·Qdrant 인증/저장/검색 | NOT VERIFIED |
| 6 | 출처 링크·원본 전체 조회·권한 없는 프로젝트 거부·무결성 검사 | NOT VERIFIED |
| 7 | 업무 질문 20~50개 검색 평가·동시 부하·실제 처리량/디스크 측정 | NOT VERIFIED |
| 8 | 백업 생성·분리 복구 디렉터리 검증·재등록·재색인 훈련 | NOT VERIFIED |

실제 서버 정보가 제공되지 않았으므로 이 환경에서 해당 서버 접속/배포/업무 데이터 검증은 수행하지 않았다.
백업 복구는 `RAW_ONLY_REBUILD_REQUIRED`이며 실 DB를 덮어쓰지 않는다. 인증·모델·벡터 설정 재등록과 재처리/재색인이 필요하다.

## 8. 중지·업데이트·문제 확인

```bash
# 데이터 보존 중지
sudo docker compose --env-file .env.intranet -p almrag-intranet \
  -f deploy/compose.intranet.yaml --profile services stop

# 업데이트 전 UI에서 백업 생성 후 보존 위치 확인
git pull --ff-only origin codex/m6-quality
sudo docker compose --env-file .env.intranet -p almrag-intranet \
  -f deploy/compose.intranet.yaml --profile services up -d --build --wait --wait-timeout 120

# 운영자 로컬에서만 로그 확인, 원본 로그는 외부 게시하지 않음
sudo docker compose --env-file .env.intranet -p almrag-intranet \
  -f deploy/compose.intranet.yaml logs --tail 100 api worker
```

401/403은 관리자 세션과 Origin 일치 여부, worker의 credential unavailable은 양쪽 env 전달과 참조 이름,
ALM origin blocked는 허용 Origin, model blocked는 프로필·digest·보정·CA, vector unavailable은 URL·API 키부터 확인한다.
HTTP 모드의 쿠키는 Secure 속성이 없으므로 이전 HTTPS 데모 쿠키와 섞일 경우 해당 호스트의 기존 쿠키를 지운 뒤 재로그인한다.

## 9. Docker 없이 영속 Native로 실행

Native는 Python3.12/uv와 Node22/npm으로 `uv sync --frozen --python 3.12`, `npm --prefix frontend ci`, `npm --prefix frontend run build`를 먼저 수행한다. Node 설치는 [기존 설치·실행 안내](GETTING_STARTED.ko.md)의 버전 조건을 따른다. 아래 주소는 실제 접속 주소로 바꾼다.

```bash
export ALMRAG_DATABASE_PATH="$PWD/data/alm.sqlite"
export ALMRAG_ATTACHMENT_ROOT="$PWD/data/attachments"
export ALMRAG_ALLOWED_ORIGIN="http://10.0.0.20:8000"
export ALMRAG_INTRANET_HTTP_ENABLED=true
uv run python -m almrag.cli migrate
uv run python -m almrag.cli bootstrap-admin
uv run python -m almrag.server --host 0.0.0.0 --port 8000
```

이 서버는 `frontend/dist`의 실제 빌드 파일과 API를 함께 제공하며 DB를 보존한다. 데모 계정은 만들지 않는다. 다른 터미널에서 **동일한 DB 경로·HTTP 설정·ALM 비밀 값/허용 Origin·Ollama/Qdrant URL·프로필·live 플래그**를 지정한 뒤 `uv run python -m almrag.worker`를 실행한다. 앱은 `.env.intranet`을 자동으로 읽지 않으며 Compose용 컨테이너 경로 `/app/config`를 Native 경로로 그대로 쓰면 안 된다.

Native CLI 관리자 로그인도 `ALMRAG_API_URL`과 `ALMRAG_ALLOWED_ORIGIN`을 위 HTTP 주소로 맞추고 `ALMRAG_INTRANET_HTTP_ENABLED=true`를 지정한 상태에서 `uv run python -m almrag.cli login`을 사용한다. 세션 파일은 해당 API 주소에 묶여 `0600`으로 저장된다. 기본 HTTPS 정책은 유지되므로 명시 설정 없이 HTTP로 관리자 세션을 보내지 않는다.

무중단 서비스 관리자 구성은 별도 systemd 운영 정책에 따르며 이 배포에서는 제공된 Compose `restart: unless-stopped` 경로를 기본으로 검증한다. 어느 방식이든 같은 DB를 Native/Compose 두 묶음에서 중복 운영하지 않는다.
