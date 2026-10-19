# Change Log — v0.1 → v0.2

- 요청: ALM별 프로젝트 입력/선택, Chunk 크기, Docker dependencies, ALM API throttle, Fail-safe/Item replay/logging, TDD.
- 정책 결정 Q01~Q50 유지. 제안 기술 수치(512/64/1024, 2 RPS)는 **사용자 확정이 아닌 실측 전 설계 초기값**.
- 추가 SRS-044..059 / TEST-044..059 및 Given/When/Then AC-09..13.
- Architecture / Data Model / Interface / OpenAPI 초안에 source_type/selection scope, token budget, RateLimitPolicy, FailedItem, replay endpoints 반영.
- 설계용 deploy/Dockerfile.backend, deploy/Dockerfile.frontend, deploy/compose.yaml, .dockerignore 작성; 소스 및 Lock 파일 미구현/미검증.
- 개발 Agent에 TDD Red→Green→Refactor 및 QA evidence 의무 추가.
- 승인 전 M1 실행 금지 정책 유지, Google/Ollama 실제 서버/model, CB/Polarion 제품버전 미검증.
