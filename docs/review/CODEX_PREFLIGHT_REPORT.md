# ALM RAG 개발 환경 사전 검증 보고서

- 검증일: 2026-10-19 (Asia/Seoul, 사용자 세션 기준)
- 대상: `/Users/skongby/projects/alm-rag`, macOS 로컬 Codex 세션
- 최초 판정: **FAIL — 기본 환경에서 Baseline 검증 불가.** 아래 최초 관찰은 이력으로 보존하며, 후속 보완 결과는 마지막 절을 우선한다.
- 최신 판정: **PASS — 문서 정적 검증, 6개 역할 smoke check, 로컬 도구 및 Docker 단일 컨테이너 실행.** M1 구현/앱 Build·Boot, 병렬 Worktree 경합 및 외부 통합은 NOT VERIFIED이며 M1은 NOT STARTED.
- 최초 범위: 문서/설정/로컬 Git/도구 점검, Baseline 스크립트 실행, 읽기 전용 QA 위임. 후속 사용자 지시로 환경 의존성 설치 및 런타임 검증을 추가했다. 애플리케이션 구현/ALM 접속/GitHub Push는 수행하지 않았다.

## 승인 및 기준 문서

AGENTS.md, BASELINE_APPROVAL.md, CODEX_PREFLIGHT.md, OPEN_ISSUES.md, MASTER_PLAN.md를 읽었다. 추가로 BASELINE_AUDIT.md, DECISION_COVERAGE.csv, M1 계획, 배포/의존성 명세, Docker 초안, 검증 스크립트를 확인했다.

| 판정 | 항목 | 근거와 한계 |
|---|---|---|
| PASS | v0.3 조건부 승인 | 환경 준비만 승인. `baseline-v0.3-conditional`은 문서 기준선이며 릴리스가 아니다. |
| PASS | M1 착수 제한 | 명시적 Start M1 지시 전 구현 금지. 이번 요청도 M1 시작을 금지함. |
| PASS | M1~M6 Human Gate | 한 단계씩 plan → design → implement → test → QA, 최대 3회 수정/재검증, 단계별 사용자 승인 후 다음 단계. 중대한 미해결 문제는 즉시 Human Review. |
| NOT VERIFIED | 원본 REQ 조항 완전성 | OI-019/OI-023 유지. 252행 또는 결정 매핑은 원문 조항 검증이 아니다. |

## Codex 및 역할 검증

| 판정 | 항목 | 실제 관찰 |
|---|---|---|
| PASS | CLI | `/opt/homebrew/bin/codex`, `codex --version`: `codex-cli 0.163.0` |
| PASS | Multi-Agent 기능 | `codex features list`: `multi_agent stable true`, `worktrees stable true` |
| PASS | 프로젝트 설정 | `approval_policy="on-request"`, `sandbox_mode="workspace-write"`, `features.multi_agent=true`, `agents.enabled=true`, `max_concurrent_threads_per_session=3` |
| PASS | TOML 및 역할 파일 | Python 3.14 tomllib로 기본 설정과 6개 역할 파일 파싱. requirements, architect, alm_collector, rag_engineer, frontend, qa의 config_file 존재 및 developer_instructions 확인. 현재 세션 도구에도 6개 역할 노출. |
| PASS | 공식 설정 계약 대조 | agents.enabled, 역할 config_file, max_concurrent_threads_per_session은 공식 문서의 현행 키. 동시 3개는 Main 제외 Subagent 수. 폐기된 프로젝트 키를 발견하지 않아 설정 수정 없음. |
| PASS | QA 실제 위임 | `/root/qa_preflight`를 `agent_type=qa`로 실행하고 최종 응답 수신. QA는 실제 전달된 developer instructions와 qa.toml 내용 일치를 확인. 읽기 전용 소유권으로 작업하여 별도 Worktree 생성 없음. |
| NOT VERIFIED | 다른 5개 역할 실행 | 파일/등록 확인만 수행. 개별 spawn과 역할 지시 전달은 미실행. |
| NOT VERIFIED | 동시 제한/Worktree 경합 | 최대 3개 제한 도달 시험, 병렬 수정 충돌/격리 시험은 미실행. Worktree 자동 격리를 가정하지 않는다. |
| PASS | 설정 및 제한 전달 | 사용자 config의 approval/sandbox 키는 UNSET, 프로젝트 trust는 trusted. 세션에는 workspace-write 및 제한된 네트워크, 관리형 파일시스템 제한이 전달됨. |
| PASS | 관찰된 승인 경로 | `uv python list --only-installed`는 sandbox 안에서 uv 캐시 읽기 권한 오류 발생. require_escalated 요청 후 승인된 동일 명령이 성공. 승인 prefix 저장됨. |
| NOT VERIFIED | 포괄적 Sandbox 강제성 | 위 관찰만으로 모든 외부 쓰기/네트워크 차단을 입증하지 않음. 의도적인 금지 쓰기 및 외부 ALM 연결 시험 없음. |
| NOT VERIFIED | CLI 전체 엄격 스키마 검사 | `codex --strict-config features list`는 exit 1, 해당 subcommand에서 strict-config 미지원. 이것은 프로젝트 설정 오류의 증거가 아니다. |

CLI 명령에는 PATH aliases 생성 불가(`Operation not permitted`) 경고가 있었으나 버전/feature 조회는 완료됐다. 설정 근거: [공식 OpenAI Configuration Reference](https://learn.chatgpt.com/docs/config-file/config-reference), 검증일에 조회. 역할 파일 경로는 선언한 설정 파일 기준 상대 경로이며, 동시 제한은 Main을 제외한다.

## Git 상태

| 판정 | 항목 | 실제 관찰 |
|---|---|---|
| PASS | Git | `git version 2.50.1 (Apple Git-155)` |
| PASS | Branch / 초기 변경사항 | `main`, upstream `origin/main`; 보고서 작성 전 `git status --porcelain=v1` 출력 없음 |
| PASS | HEAD | `078a5bf0991840f6c060f95cc315670173228de5` — `docs: approve v0.3 conditional baseline and prepare Codex/GitHub setup` |
| PASS | Baseline tag | annotated tag object `ffed6fb6c1927fed915303a75733f904d35e239a`; peeled commit은 HEAD와 동일 |
| PASS | 로컬 추적 참조 | HEAD...origin/main ahead/behind `0 / 0`. 로컬 저장 참조끼리의 비교만 수행. |
| PASS | 원격 설정 존재 | origin = `https://github.com/Benjamin-Kong/alm-rag.git` |
| NOT VERIFIED | 원격 최신성/권한/비공개 여부 | fetch/ls-remote/API/Push 미실행. 원격 설정 존재는 접근권한 또는 Push 승인 증거가 아님. |
| PASS | Worktree 목록 | 현재 main checkout 1개. 추가 Worktree 생성 없음. |

Commit의 기록 시각은 `2026-10-19T13:14:42Z`. 최초 점검은 이 보고서와 OPEN_ISSUES 추기만 변경했다. 후속 보완은 CODEX_PREFLIGHT.md와 tools/requirements.preflight.txt도 포함한다. commit/tag/branch/remote는 변경하지 않았다.

## Baseline 실제 실행 증거

**FAIL — 요청된 명령**, exit code 1:

```text
$ python3 tools/validate_baseline.py
Traceback (most recent call last):
  File "/Users/skongby/projects/alm-rag/tools/validate_baseline.py", line 5, in <module>
    import csv, json, re, tomllib, hashlib, sys
ModuleNotFoundError: No module named 'tomllib'
```

`python3`는 `/usr/bin/python3`, 버전 3.9.6이다.

**FAIL — 설치된 Python 3.12로 추가 실행**, exit code 2:

```text
$ /Users/skongby/.local/share/uv/python/cpython-3.12.12-macos-aarch64-none/bin/python3.12 tools/validate_baseline.py
BLOCKED: PyYAML is required for schema validation
```

Codex bundled Python(`/Users/skongby/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`)으로도 exit 2, 동일 PyYAML 오류. 스크립트를 수정하거나 의존성을 설치하지 않았다.

**NOT VERIFIED — 전체 DOC_STATIC_PASS:** 검증 본문 완료 전에 의존성 오류로 중단됨. 별도 TOML 파싱 성공을 전체 Baseline PASS로 대체하지 않는다. 향후 정적 PASS도 애플리케이션/DB/ALM/Docker 테스트 PASS를 의미하지 않는다.

## M1 도구와 의존성

| 판정 | 항목 | 실제 관찰 및 다음 단계 |
|---|---|---|
| PASS | Python 3.12 설치 | uv 설치 목록과 직접 실행으로 3.12.12 확인. SQLite 모듈 3.50.4. DB 생성/동시성 시험은 하지 않음. |
| FAIL | 기본 Python/검증 의존성 | 기본 Python 3.9.6은 tomllib 없음. 3.12 환경도 PyYAML 없음. 명시적인 검증용 환경과 의존성 준비 필요. |
| PASS | Python 도구 | uv 0.9.18, 추가 Homebrew Python 3.14.8 존재 |
| PASS | Node/패키지 관리자 존재 | Node v25.8.0, npm 11.11.0, pnpm 11.25.0 |
| NOT VERIFIED | Node 재현성 | Docker 초안 node:22-alpine과 로컬 Node 25가 다름. 프로젝트 엔진/lock 기준 확정 및 호환성 시험 전 준비 완료 선언 불가. |
| FAIL | Docker 도구 발견 | PATH에서 docker와 docker-compose를 찾지 못함. `/Applications/Docker.app`도 없음. 다른 위치/대체 런타임 존재 여부는 미확인. |
| PASS | 보조 CLI 존재 | gh 2.102.0; ollama 실행 파일 `/opt/homebrew/bin/ollama` 발견. GitHub 인증 및 Ollama 서비스/모델은 미조회. |
| NOT VERIFIED | M1 프로젝트 의존성 환경 | `.venv`, pyproject.toml, uv.lock, 루트 package.json/package-lock.json, .github/workflows 없음. M1에서 생성할 산출물이며 이번 작업에서 만들지 않음. |
| NOT VERIFIED | 앱/테스트 실행 준비 | 아래 후보 패키지는 검사한 Python 3.12 interpreter에 미설치. 프로젝트 lock/소스가 없어 설치·실행 검증 미수행. |
| NOT VERIFIED | Build/Boot/연결 | Docker/Native 앱, Qdrant/Ollama, 실제 ALM, 인증/Queue restart, mock E2E 및 CI 테스트 미실행 |

Python 3.12에서 importlib.metadata로 확인한 미설치 패키지: PyYAML, fastapi, uvicorn, pydantic, pydantic-settings, sqlalchemy, alembic, httpx, tenacity, anyio, cryptography, argon2-cffi, lxml, beautifulsoup4, qdrant-client, structlog, typer, pytest, pytest-asyncio, respx, hypothesis, coverage. 이는 해당 interpreter의 상태이며 다른 환경에 대한 전역 부재 주장이 아니다.

## 후속 조치와 종료

1. 환경 보완 시 Python 3.12 검증 환경과 PyYAML을 준비하고 동일 Baseline 명령을 재실행하여 실제 결과를 남긴다.
2. Docker/Compose 제공 경로와 Node 기준을 정하고 도구 가용성을 재검증한다. 앱 소스/lock/Build/Boot는 M1 승인 이후 산출물이다.
3. 나머지 역할 실행 및 병렬 Worktree 운용 증거, 원격 접근과 별도 Push 승인 여부를 각각 확인한다.
4. OI-019/OI-023은 열린 상태로 유지한다. M1~M6 테스트 성공을 선언하지 않는다.

**M1: NOT STARTED. 환경 검증 결과를 제출하고 사용자 지시를 기다린다.**

## 후속 보완 — 사용자 “보완하고 진행해봐” 지시

환경 준비 보완으로 해석하고 M1 착수 제한을 유지했다. 최초 FAIL 기록을 삭제하지 않고 재검증 결과를 추가한다.

| 판정 | 항목 | 보완 및 실제 결과 |
|---|---|---|
| PASS | 검증용 Python | 설치된 Python 3.12.12로 Git 제외 `.venv` 생성, PyYAML 6.0.3 설치. `tools/requirements.preflight.txt`에 문서 검증용 버전 고정. 시스템 Python은 변경하지 않음. |
| PASS | Baseline 재실행 | `.venv` 활성화 후 `python3 tools/validate_baseline.py`, exit 0. 50 decisions / 252 legacy rows / 59 SRS / 59 assigned tests / 6 subagents / 36 draft API operations / YAML+TOML valid. |
| PASS | Node 환경 | Homebrew node@22 설치. 세션 PATH 지정으로 Node v22.23.3 / npm 10.9.9 확인. 기존 전역 Node 25 및 shell profile은 유지. |
| PASS | Docker 도구 설치 | Docker CLI 29.9.1, standalone Docker Compose 5.6.0, Colima 0.10.3, Lima 2.2.1 설치. |
| PASS | Compose 정적 구성 | `docker-compose -f deploy/compose.yaml config --quiet`, exit 0. 앱 build/boot가 아닌 Compose 파싱 검사. |
| PASS | 나머지 역할 smoke check | requirements_smoke, architect_smoke, collector_smoke, rag_smoke, frontend_smoke 각각 해당 agent_type으로 실행하고 역할 파일과 실제 developer instructions 일치 응답 수신. 기존 qa_preflight와 합쳐 6개 모두 실행 확인. 읽기 전용이며 파일 수정/네트워크/추가 위임 없음. |
| NOT VERIFIED | 병렬 수정 격리 | 읽기 전용 역할 확인에는 Worktree를 만들지 않음. 동시 상한/Worktree 경합 강제 시험은 여전히 미실행. |
| NOT VERIFIED | 제품 기능 및 원격 검증 | M1 앱/lock/CI, ALM, Qdrant/Ollama, GitHub 원격 최신성/접근권한, Legacy 조항 원문 검증은 기존 Gate에 유지. |

실제 재실행 출력(exit 0):

```text
DOC_STATIC_PASS: 50 decisions, 252 legacy mapping rows, 59 SRS, 59 assigned milestones/tests, 6 subagents, 36 draft API operations, YAML+TOML valid
LIMITATIONS: original legacy REQ text unavailable; no live backend, database, ALM, Docker, model, Codex runtime tests executed
```

위 LIMITATIONS는 정적 스크립트 자체의 범위를 설명하는 고정 문구다. 별도로 수행한 역할 smoke check와 런타임 검증은 본 보고서의 해당 증거로만 판정한다.

설치는 승인된 elevated 명령으로 수행했다. Homebrew는 c-ares/libnghttp2/libnghttp3/libuv/simdjson/sqlite 의존성도 갱신했다. 신뢰되지 않은 기존 tap 경고에는 trust 설정을 변경하지 않았다. 재현 명령은 `docs/governance/CODEX_PREFLIGHT.md`에 기록했다.

### Docker 런타임 실제 검증

- PASS: `colima start alm-rag --cpu 2 --memory 2 --disk 20 --mount none --activate=false --ssh-config=false`, exit 0. 전용 VM/context 생성, 홈 디렉터리 공유 및 기본 context 변경 없음.
- PASS: `docker --context colima-alm-rag version`, exit 0. Client 29.9.1 / Server 29.5.2, linux/arm64, 협상 API 1.54.
- PASS: `docker --context colima-alm-rag run --rm hello-world`, exit 0, `Hello from Docker!`. 공식 이미지 digest `sha256:11a3eb1597e864c51b3f56733cb2e8a90bf0c284bfc05f9444d81c558bc848aa`.
- 이 검증은 프로젝트 이미지 build/boot가 아니다. 앱 Compose 서비스 및 ALM/Qdrant/Ollama는 실행·접속하지 않았다.
- VM 시작 및 Docker socket/이미지 다운로드는 별도 host 실행 승인 경로를 거쳤다. 데이터 업로드나 Git Push는 없었다.
- 독립 QA가 `.venv/bin/python tools/validate_baseline.py`를 재실행하여 exit 0을 확인했다. QA의 변경 파일 설명/절 제목 지적을 반영했다. Docker 결과는 Main의 실제 실행 증거이며 QA가 독립 재실행한 결과로 주장하지 않는다.
- PASS: 검증 후 `colima stop alm-rag`, exit 0. VM은 종료됐고 재사용 가능한 설정/이미지는 남겨 두었다. `docker context show`는 `default`; Colima 설정의 autoActivate=false, sshConfig=false, CPU=2, memory=2, disk=20 확인.

최종 변경: `docs/governance/CODEX_PREFLIGHT.md`, `docs/review/CODEX_PREFLIGHT_REPORT.md`, `docs/review/OPEN_ISSUES.md`, `tools/requirements.preflight.txt`. `git diff --check` 통과. M1 구현은 시작하지 않았으며 사용자 착수 지시를 기다린다.
