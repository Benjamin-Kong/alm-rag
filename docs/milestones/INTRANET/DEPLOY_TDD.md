# 사내 Linux 배포·진단 TDD 증거

2026-10-21. 사용자 승인: 사내 HTTP 사용, 실사용 준비 구현, 실 Linux 서버의 ALM/DB/Ollama 검증 절차 제공.
범위: SRS-025..029(운영·배포 관련 추적), SRS-051/052/059(환경·보안·검증 관련 추적).
원래 복원되지 않은 legacy REQ 조항을 새로 정의하지 않는다. 정확한 적용 범위는 기존 TRACEABILITY의 Primary/Shared를 유지한다.

소유 worktree: `.worktrees/intranet-deploy`. 다른 작업자의 설정/인증/모델 구현 파일은 수정하지 않았다.

## Red → Green 실제 실행

모든 pytest 실행은 worktree 루트에서 다음 명령을 사용했다. 루트 가상환경을 재사용하되 worktree 소스를 명시했다.

```bash
PYTHONPATH=src /Users/skongby/projects/alm-rag/.venv/bin/pytest -q tests/test_server_doctor.py
```

| 단계 | 실제 결과 | 원인/의미 |
|---|---|---|
| 초기 Red | collection ERROR, exit 2, 0.26초 | `ModuleNotFoundError: almrag.doctor`. 신규 진단 모듈 구현 전 5개 테스트 작성 |
| 첫 Green | 5 passed, 0.24초 | 오프라인 무접속·미생성, 기존 SQLite 읽기 전용, 손상 DB 마스킹, 명시 서비스 probe, schema drift 검사 |
| ALM probe Red | 1 failed, 5 passed, 0.22초 | 실제 connector 계약은 `read_only/project_count`이며 임의 `ok/status` 값이 아님 |
| ALM Green | 6 passed, 0.18초 | 공유 connector의 실제 읽기 전용 probe 반환 계약 적용 |
| vault 미생성 Red | 1 failed, 6 passed, 0.23초 | `vault:` lookup이 없는 DB를 생성함. 서비스 점검도 없는 DB를 만들지 않아야 함 |
| vault Green | 7 passed, 0.17초 | vault lookup 이전 DB 존재 검사, 비밀정보 없는 고정 오류 반환 |
| 최종 회귀 | 9 passed, 0.28초 | 모듈/도구 CLI 출력·종료코드, Compose 공유 env/비공개 포트/readonly mount 검사 추가 |

추가 실제 실행:

```bash
docker-compose --env-file /private/tmp/almrag-intranet-compose-test.env \
  -f deploy/compose.intranet.yaml --profile services config --quiet
```

exit 0, Compose 구문·interpolation·profile 파싱 PASS. 임시 env에는 합성 키만 사용했고 외부 서버에 접속하지 않았다.

```bash
PYTHONPATH=src /Users/skongby/projects/alm-rag/.venv/bin/python tools/check_server.py
```

exit 0, 런타임·스토리지 상위 경로 PASS 2, SQLite/모델/ALM/Ollama/Qdrant NOT VERIFIED 5, FAIL 0.
`git diff --check`: exit 0. 신규 파일은 루트 통합 시 다시 검사한다.

## 설계와 한계

- `python -m almrag.doctor`는 backend wheel/image에서도 사용 가능하며 `tools/check_server.py`는 같은 CLI를 위임한다.
- 기본 진단은 네트워크 접속·마이그레이션·없는 DB 생성을 수행하지 않는다. 기존 DB는 URI `mode=ro`, `query_only`로 검사한다.
- `--services`는 Ollama/Qdrant GET만 명시적으로 허용하며 공유 ServiceProbe·자격증명 resolver를 사용한다.
- `--alm-instance`는 live flag·허용 Origin·기존 프로필을 요구하고 공유 connector/rate-limit transport로 조회한다. 로컬 rate-limit 상태 기록은 가능하지만 ALM 콘텐츠는 수정하지 않는다.
- 출력은 고정 코드와 상태만 사용하며 예외 문자열·주소·실제 UID·고객 본문·비밀정보를 기록하지 않는다.
- 프로필 정적 PASS는 실제 토큰 수 보정/모델 추론 검증을 대신하지 않는다. SQLite 구조 PASS는 Item/Chunk/벡터 의미적 무결성을 대신하지 않는다.
- Compose는 config/docs 변경으로 별도 runtime Red 대상이 아니다(TDD_POLICY config/docs 예외). 기존 base 파일과 합치지 않는 standalone 구성이다.
- API·Worker에 private env file을 동일하게 전달한다. 실제 secret 값은 Git 제외 `.env.intranet`에만 보관한다.
- API/벡터 포트는 직접 공개하지 않으며 nginx 8080만 설정된 bind 주소에 게시한다. 내장 Qdrant는 인증 키를 필수로 요구한다.
- 여기서는 실제 Compose Build/Boot, 실서버 HTTP 로그인, 실제 ALM/Ollama/Qdrant 업무 데이터 연결을 실행하지 않았다. **NOT VERIFIED**이며 루트 통합/실서버 검증 결과로 보완한다.
