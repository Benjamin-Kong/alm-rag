# M6 execution portability evidence

| Mode | Actual status | Evidence / limits |
|---|---|---|
| macOS arm64 Native Python3.12 + Node22 | PASS tested local scope | unit/integration/CLI/worker/wheel; actual Chromium→native HTTPS API/session/CSRF/worker |
| Linux arm64 API/worker/frontend containers in Colima | PASS tested local scope | digest-pinned builds, non-root3service boot, volumes/migrations, network-none synthetic runtime smokes |
| Local Qdrant Linux container from Native macOS | PASS | actual scoped query/index/rebuild/crash and M6 quality/vector corruption tests; synthetic owned collections only |
| Windows Native / Windows Docker host | NOT VERIFIED | no Windows host/runtime supplied; use uv Python3.12 + Node22 + Docker-compatible local services and run same gates before claiming support |
| Linux Native host / amd64 images | NOT VERIFIED | current Linux evidence is arm64 containers, not all host/runtime modes |
| Actual local/remote Ollama, CPU/GPU/remote embedding | NOT VERIFIED | no calibrated real model/tokenizer artifacts and no live model access authorized |
| Actual remote Qdrant/TLS/private-network deployment | NOT VERIFIED | configuration/transport mocks implemented; only dedicated loopback Qdrant actually exercised |
| Production HTTPS reverse proxy/deployment | NOT VERIFIED | disposable native HTTPS proves browser session contract, not production certificate/proxy rollout |
| Remote GitHub CI / OS image vulnerability scan | NOT VERIFIED | CI gate config present; no Push/remote runner/OS scanner execution |

Retained environment findings: bare system Python3.9 cannot execute TOML baseline validator; use .venv3.12. Default Node25 dylib is broken; use explicitly tested Node22. These global installations were not rewritten. No actual customer ALM or model access, Push, remote Notion publication, production deployment or destructive customer DB operation performed.
