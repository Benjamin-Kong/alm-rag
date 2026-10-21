# ADR-003: 명시적 사내 HTTP 실행 모드

상태: 사용자의 사내 HTTP 선택에 따라 구현. 기존 HTTPS 기본값 유지.

웹 UI 로그인은 기본 Secure 쿠키를 사용하므로 HTTP에서 사용할 수 없었다. 사용자가 HTTPS 미적용 사내망 운영과 실제 Linux 검증용 구현을 명시했다. `ALMRAG_INTRANET_HTTP_ENABLED=true`와 정확한 HTTP `ALMRAG_ALLOWED_ORIGIN`을 함께 지정한 경우에만 세션 쿠키의 Secure 속성을 끈다. HttpOnly·SameSite=strict·Origin·CSRF·프로젝트 ACL·감사 기록은 유지한다. HTTPS Origin에는 플래그와 무관하게 Secure 쿠키를 사용한다. 오타 플래그와 명시적 허용 없는 HTTP Origin은 기동 설정 오류다. CLI도 같은 플래그·Origin 일치를 요구한다. HTTP 구간은 암호화되지 않으며 사용자가 지정한 사내 접근망에서만 운용한다.

영속 Native 진입점 `python -m almrag.server`는 빌드된 UI와 API를 같은 Origin으로 제공한다. 정적 파일은 별도 디렉터리만 제공하고 모든 `/api/` 경로는 기존 인증 경계를 거친다. 데모 계정·임시 DB를 생성하지 않는다. Worker는 별도 프로세스이며 동일 로컬 SQLite를 사용한다. 별도 사내 Compose는 환경 파일을 API·Worker에 같이 전달하고 설정 디렉터리 읽기 전용 마운트, 영속 볼륨, 재시작 정책과 인증된 선택적 Qdrant를 제공한다.

실제 연동은 오프라인 기본 doctor/명시적 읽기 probe와 모델 프로필 생성·교정 도구로 검증한다. 모델·토크나이저 자동 다운로드, 무검증 fallback, 원본 ALM 쓰기, 외부 SQL DB 지원은 추가하지 않는다. 운영자 아티팩트는 Git·Docker build context에서 제외한다. 실제 고객 ALM/모델/전체100k 파이프라인과 운영 복구 전환은 실행 전까지 NOT VERIFIED다.

근거: DECISIONS 추가 결정, INTRANET/PLAN·HTTP_TDD·DEPLOY_TDD·MODEL_TDD. Ollama 응답의 raw64hex digest와 기본 태그 표현은 공식 [tags](https://docs.ollama.com/api/tags) 형식에 맞춰 동등 표현만 정규화한다. 잘못된 digest·태그·모호한 중복은 계속 거부한다.
