# Docker / Native 배포 및 종속성 명세 — v0.2 Draft

## M6 current runtime supplement — 2026-10-21

M1..M6 sources, frozen locks,55 executable API operations and React console are implemented locally. M6/RUNBOOK.md and PORTABILITY.md supersede historical stage/skeleton claims below. Local macOS arm64 Native and Linux arm64 API/worker/frontend images plus actual dedicated Qdrant are tested. Actual ALM/model/remote Notion, other host OS/amd64/remote CI and production deployment remain NOT VERIFIED. Default live ALM/model/vector/summary flags are false; raw-only recovery requires rebuilding search and re-registering authentication.

## M1 implementation supplement — 2026-10-20 (supersedes skeleton claims below)

API/Worker and Frontend images now build and boot locally; evidence is in `docs/milestones/M1/TEST_REPORT.md`. M1 uses Python 3.12, stdlib sqlite3 + transactional SQL migrations, FastAPI/Uvicorn, httpx, Argon2, cryptography and Typer. Actual resolved versions/hashes are in pyproject.toml/uv.lock. React/TypeScript/Vite, Vitest 5.0.5 and generated OpenAPI tooling are in frontend/package-lock.json. Unneeded candidate SQLAlchemy/Alembic/HTML/index libraries are not installed before their implementation milestones.

Base images and uv build tool are digest pinned. API and worker run UID10001; frontend Nginx UID101. Healthchecks, shared local volume and loopback ports are exercised. Native install and independent CLI/Worker run on macOS; Linux containers run in Colima. Qdrant is an optional Compose `services` profile with a pinned image; Ollama/Qdrant remote settings are configured and mocked but real services are NOT VERIFIED. Windows/native Linux and remote CI are NOT VERIFIED.

The legacy requirements.backend.in is a candidate inventory only and is no longer installed by Docker. Run instructions and HTTPS/session constraints are in M1/RUNBOOK.md. The historical sections below retain the original candidate rationale; they are not current execution claims.

## 1. 배포
- **Backend API**: Python 3.12-slim, FastAPI, Uvicorn; React 정적 UI와 독립 배포 가능.
- **Worker**: 동일 Python 이미지 재사용, 별도 `almrag.worker` Entry Point. UI/검색 응답 프로세스와 분리.
- **Frontend**: Node LTS Build Stage → 정적 Nginx Runtime(일반 쓰기 금지, read-only RootFS 여부는 실제 확인).
- **SQLite**: API/Worker가 동시에 접근하는 경우 동일 로컬 볼륨·동일 호스트 원칙. NFS/복수 Docker 호스트에 공유 SQLite를 배치하는 구성은 기본 지원하지 않는다.
- **Qdrant**: 별도 서비스 컨테이너 또는 HTTPS 원격 Qdrant. Persistent volume. 변경/재시작 시 실서비스 스토리지 정합성 테스트.
- **Ollama**: Native Host / Remote Ollama 기본. Docker 내부 Ollama 서비스는 별도 옵션/Compose profile로 도입 가능. 컨테이너에서 `localhost`는 Host가 아닌 해당 컨테이너를 의미하므로 URL을 분리.

## 2. 이미지 포함 라이브러리(후보, 버전은 M1 lock 파일에서 고정)
| 영역 | 패키지/도구 | 이유 |
|---|---|---|
| Core API | python3.12, fastapi, uvicorn, pydantic, pydantic-settings | REST, config, validation |
| DB | sqlalchemy, alembic, SQLite native libraries | Metadata, revision, migration |
| HTTP & Retry | httpx, tenacity, anyio | ALM 및 Ollama API, timeout/backoff |
| Auth | cryptography, argon2-cffi | Secret at-rest, password hash |
| HTML | lxml, beautifulsoup4, html5lib(선택) | 복잡한 문서 DOM/Table |
| Qdrant | qdrant-client | Dense index + query |
| Logging/CLI | structlog, typer | JSON logs, admin CLI |
| Testing (dev image) | pytest, pytest-asyncio, respx, hypothesis, coverage | Unit/contract/property tests |
| Frontend build | Node LTS, npm ci, React, TypeScript, Vite | Web UI |
| Runtime utility | ca-certificates, OS timezone data(필요 시), tini/dumb-init(필요 시) | TLS + graceful shutdown |

선택적 기능이 확정되지 않았으면 이미지에 모든 패키지를 넣지 않는다. OCR/Docling/SpaCy/LLM을 요구사항 밖에서 자동 추가하지 않는다. 개발/테스트 의존성은 런타임 이미지에서 분리한다.

## 3. 빌드 보안 및 품질
- `deploy/Dockerfile.backend`, `deploy/Dockerfile.frontend`, `deploy/compose.yaml`은 **설계용 Skeleton**. 현재 Backend/Frontend 소스·lock files가 없으므로 실제 build/boot 테스트 불가능.
- Dockerfile: multi-stage / 비루트 실행 / 정규화된 `/app/data` 볼륨 / `.dockerignore` / 이미지/패키지 고정 / healthcheck / 1개 프로세스당 컨테이너.
- CI: `docker build` 두 이미지, Compose `config` 검증, API/Worker/Frontend start, Qdrant ready, Health Checks, 실제 Container Network에서 Host Ollama URL vs Remote URL 검사.
- 재현성: Python/Node Lock file은 **M1 구현 시 생성한 뒤 pinned 버전·해시 정책으로 관리**. Skeleton은 기능 코드가 없어 `docker build`를 통과한다고 주장하지 않는다.
- Secrets: `.env`가 이미지를 포함해 Docker build context로 들어가지 않게 `.dockerignore`, 런타임 환경 변수/secret mounts를 사용. 외부 ALM 접근/Private GitHub/Notion에는 실데이터 업로드 금지.
- OS 차이: Linux container 사용을 기본으로 하며 Windows/macOS는 Docker Desktop/동등 런타임을 통한 실행을 별도 검증. Native mode의 OS별 별도 안내서를 유지.

## 4. Docker test & rollout
M1에서 이미지 Build/Boot/Health와 임시 SQLite migration+Qdrant 연결을 검증하고 M6에서 환경별 실제 성능을 측정한다. 컨테이너가 중단될 때 각 서비스가 단계별 Checkpoint 및 잠금을 해제/재개하는지 검증한다.

## 5. v0.2 Runtime package installation scaffold
`deploy/requirements.backend.in` lists candidate Python runtime packages and `deploy/Dockerfile.backend` **installs** them with pip. This is design scaffold only; packages are NOT version-locked and application modules are still missing, so it does not meet release reproducibility or runnability. M1 must generate/verify hash-locked dependency files and replace temporary installation strategy. Frontend Dockerfile awaits React/Vite package-lock and source.
