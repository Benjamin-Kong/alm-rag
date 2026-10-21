# Ollama 모델·토크나이저 운영 설정

이 문서는 Linux 운영자가 실제 모델 서버에서 검증하는 절차입니다. 개발 테스트에서 사용한 합성 토크나이저·벡터·모델 digest를 운영 설정에 복사하면 안 됩니다. 실제 Ollama와 승인된 토크나이저로 실행하기 전 상태는 **NOT VERIFIED**입니다.

## 1. 준비물

- 저장소 루트에서 `uv sync --frozen --python 3.12`를 완료합니다. Python `tokenizers`와 `httpx`는 프로젝트 잠금 파일로 설치됩니다.
- 승인된 Ollama 서버의 HTTP 주소, 모델 전체 이름·태그, 실제 SHA-256 digest, 출력 벡터 차원, 실제 입력 토큰 한도를 확인합니다.
- **동일 모델에 대응하는 실제 `tokenizer.json`**과 별도 신뢰 경로에서 확인한 SHA-256을 준비합니다. 도구는 모델이나 토크나이저를 다운로드하지 않습니다.
- 현재 승인된 런타임 모델명은 `embeddinggemma-2` 또는 `embeddinggemma-2:<태그>`입니다. 다른 이름의 모델을 임의로 이름만 바꿔 사용하거나, 임의 digest/차원을 작성하면 안 됩니다. 해당 모델의 실제 가용성·토크나이저 일치성은 서버에서 확인해야 합니다.

Ollama가 제공하는 토크나이저 동작과 `tokenizer.json`의 special token 처리까지 일치해야 합니다. 이름이 비슷한 모델의 토크나이저로 대체하거나 토큰 수 검증을 끄지 마세요. 실제 `prompt_eval_count`가 로컬 계산과 다르면 검증과 업무 처리를 중단합니다.

## 2. 서버 모델 정보 확인

아래 주소를 실제 승인된 Ollama 주소로 변경합니다. 애플리케이션 주소·ALM 주소와 구분합니다.

```bash
export ALMRAG_OLLAMA_BASE_URL='http://ollama.internal:11434'
curl --fail --silent --show-error "$ALMRAG_OLLAMA_BASE_URL/api/tags"
```

`models` 배열에서 사용할 모델의 `name`과 전체 `digest`를 확인하고 운영 설정으로 승인합니다. Ollama `/api/tags`는 [공식 응답 예시](https://docs.ollama.com/api/tags)처럼 `sha256:` 접두사 없는 64자리 해시를 반환할 수 있습니다. 프로필 생성 인자에는 접두사를 붙여 `sha256:<64자리 소문자 16진수>`로 입력합니다. 이미 접두사가 있으면 다시 붙이지 않습니다. 런타임은 서버의 두 표현을 동일한 고정 digest로 비교합니다. 모델명의 태그 생략과 `:latest`만 동등하게 취급하며 다른 태그·다른 해시는 허용하지 않습니다. `/api/show`의 context 길이와 모델 공급자의 실제 차원 정보도 확인하세요. 서버 응답을 Git에 저장하지 마세요.

모델 게이트웨이가 Bearer 인증을 요구한다면 프로세스를 실행할 터미널에서 값을 숨김 입력합니다.

```bash
read -r -s -p '모델 게이트웨이 토큰: ' ALMRAG_MODEL_GATEWAY_TOKEN
echo
export ALMRAG_MODEL_GATEWAY_TOKEN
export ALMRAG_OLLAMA_AUTH_REF='env:ALMRAG_MODEL_GATEWAY_TOKEN'
```

위 `curl` 예시는 인증 없는 서버용입니다. 토큰을 명령행 문자열에 직접 쓰지 마세요. 프로필 준비 도구의 `--verify`는 위 환경변수 참조를 해석합니다. 준비 도구는 DB를 열지 않으므로 `vault:` 참조는 지원하지 않습니다. 실행 중 API·Worker의 모델 런타임은 기존 비밀 저장소 정책을 그대로 사용합니다. 사내 CA가 필요한 HTTPS 모델 서버에는 `ALMRAG_CA_BUNDLE`을 지정합니다.

## 3. 오프라인 프로필 생성

저장소 루트에서 프로필과 토크나이저를 같은 디렉터리에 배치합니다. `config`는 실제 운영 아티팩트용 로컬 디렉터리이며 Git에 추가하지 않습니다. 배포 구성에서 다른 경로를 사용하면 경로를 함께 바꾸세요.

```bash
mkdir -p config
chmod 700 config
# 승인된 실제 파일을 config/tokenizer.json 위치에 준비한 뒤 확인합니다.
sha256sum config/tokenizer.json
```

다음 값을 실제 승인 값으로 바꾸고 실행합니다. `TOKENIZER_SHA256`은 별도 신뢰 경로의 예상 값과 위 명령 결과가 일치해야 합니다. 아래 값은 채워야 하는 자리 표시자입니다.

```bash
export TOKENIZER_SHA256='실제_64자리_SHA256'
export MODEL_DIGEST='sha256:실제_64자리_digest'
export MODEL_DIMENSION='실제_벡터_차원'
export MODEL_MAX_INPUT_TOKENS='실제_입력_토큰_한도'

uv run python tools/prepare_model_profile.py \
  --tokenizer config/tokenizer.json \
  --tokenizer-sha256 "$TOKENIZER_SHA256" \
  --model embeddinggemma-2 \
  --digest "$MODEL_DIGEST" \
  --dimension "$MODEL_DIMENSION" \
  --max-input-tokens "$MODEL_MAX_INPUT_TOKENS" \
  --output config/model-profile.json
```

기본 실행은 **네트워크를 사용하지 않습니다**. 토크나이저 해시·로딩과 설정 형식을 검증한 뒤 `NOT_VERIFIED`를 출력합니다. 이를 모델 연동 PASS로 해석하면 안 됩니다.

파일 권한은 `0600`이며 완성된 JSON을 원자적으로 게시합니다. 기존 파일은 기본적으로 덮어쓰지 않습니다. 프로필에 검증 완료 상태·비밀번호·URL·본문은 저장하지 않습니다. 토크나이저 경로는 프로필 디렉터리를 기준으로 한 상대 경로입니다.

## 4. 실제 Ollama 연동 검증

이 명령은 **명시적으로 실제 모델 서버에 연결**합니다. `--verify`는 실행의 외부 접속 동의 역할을 하므로 준비 도구 자체에는 `ALMRAG_LIVE_MODEL_ENABLED=true`가 필요하지 않습니다. 업무용 API·Worker에서는 해당 플래그가 별도로 필요합니다.

```bash
uv run python tools/prepare_model_profile.py \
  --tokenizer config/tokenizer.json \
  --tokenizer-sha256 "$TOKENIZER_SHA256" \
  --model embeddinggemma-2 \
  --digest "$MODEL_DIGEST" \
  --dimension "$MODEL_DIMENSION" \
  --max-input-tokens "$MODEL_MAX_INPUT_TOKENS" \
  --output config/model-profile.json --overwrite --verify
```

도구는 `/api/tags`의 digest, `/api/show`의 embedding capability/context 길이, 영어·한글의 실제 `/api/embed` 벡터 차원과 `prompt_eval_count`, 마지막 digest를 확인합니다. `truncate:false`로 호출하며 조용한 입력 잘림을 허용하지 않습니다. 전송되는 본문은 도구에 고정된 짧은 합성 교정 문장 두 개이며 ALM 자료는 사용하지 않습니다.

성공한 실제 연결은 `state: VERIFIED`와 문장 해시·토큰 수를 출력합니다. 성공 상태는 **그 시점의 교정 검증**이며 검색 품질·처리량·모든 길이의 문장에 대한 교정 증명은 아닙니다. 실제 업무 입력마다 토큰 수·digest 검증이 계속 적용됩니다. 테스트에서 주입한 모의 서버는 `FIXTURE_ONLY`이며 실제 검증으로 승격되지 않습니다.

실패하면 종료 코드 `1`과 안정된 오류 코드만 출력하고 새 프로필을 게시하지 않습니다. `--overwrite` 중 실패하면 기존 파일을 보존합니다. 기존 파일이 있다는 사실을 이번 검증 성공으로 해석하지 마세요. `MODEL_DIGEST_MISMATCH`, `TOKENIZER_MISMATCH`, `VECTOR_INTEGRITY_ERROR`, `MODEL_CONTEXT_UNVERIFIED` 등이면 운영자에게 모델·아티팩트 정합성을 확인하도록 합니다. 비교 검증을 우회하지 않습니다.

## 5. API·Worker에 전달

```bash
export ALMRAG_MODEL_PROFILE_PATH="$PWD/config/model-profile.json"
export ALMRAG_LIVE_MODEL_ENABLED=true
```

두 프로세스에 동일한 프로필·토크나이저·Ollama 주소·비밀 참조를 전달하고 다시 시작합니다. 앱은 `.env`를 자동 로드하지 않습니다. Compose에서는 배포 문서가 지정한 환경 파일과 마운트를 사용합니다.

컨테이너에는 프로필과 토크나이저 디렉터리를 함께 `/app/config:ro`에 마운트하고 `ALMRAG_MODEL_PROFILE_PATH=/app/config/model-profile.json`으로 지정할 수 있습니다. 파일의 소유권·권한은 non-root 컨테이너 UID가 읽을 수 있도록 **배포 담당자가 지정**해야 합니다. 호스트에서 생성한 파일이 `0600`이면 다른 UID의 컨테이너가 바로 읽을 수 없으므로 전용 그룹·최소 읽기 권한을 적용하세요. 전역 쓰기 권한을 부여하지 않습니다. 상대 경로가 디렉터리 밖을 가리키면 해당 아티팩트도 동일한 상대 위치로 마운트하거나 프로필을 다시 생성합니다.

호스트의 `127.0.0.1`은 컨테이너의 Ollama 주소가 아닙니다. 컨테이너에서 접근 가능한 사내 DNS/게이트웨이 주소를 사용하고 Worker에서도 실제 검증하세요. 호스트 교정 성공만으로 컨테이너 연결까지 PASS라고 보고하지 않습니다.

API·Worker는 프로필 JSON의 과거 검증 상태를 신뢰하지 않으며 각 런타임에서 다시 교정합니다. 이후 작은 승인된 프로젝트에서 수집 → 처리 → 임베딩 → Qdrant 게시 → 검색까지 검증하고 결과를 별도로 기록합니다. 실제 모델 품질·처리량·사내 ALM 전체 경로는 대상 서버 실행 전까지 **NOT VERIFIED**입니다.
