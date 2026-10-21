# Intranet HTTP runtime readiness

User explicitly selects internal HTTP without HTTPS and authorizes remaining implementation, commit and remote reflection; actual ALM/SQLite/Qdrant/Ollama integration will be tested on their Linux server. This authorizes configurable HTTP browser/CLI sessions; preserve existing ACL/CSRF/Origin protection, default HTTPS secure cookies, ALM read-only and explicit live-service opt-in. No actual server supplied; no access to customer services here.

Scope SRS019/025..029/038/044..059: persistent same-origin Native UI+API entrypoint; explicit HTTP configuration; deployable intranet Compose/API/worker/environment/config mounts and restart policies; offline-first runtime doctor and opt-in read-only actual connection checks; hash-pinned local tokenizer/model profile preparation and calibration; Korean install/config/use/acceptance documentation; mockintegration/negativeauth/browser/build/boot/independentQA. SQLite remains local same-host source DB; Qdrant is search index, no new external relational DB product. No silent tokenizer fallback or invented model verification.

Owners: root config.py/api.py/cli.py/server.py/auth+server tests/frontendbrowserconfig+documentationintegration; isolated intranet-deploy worktree owns deployment/doctor/Linuxrunbook; isolated intranet-model worktree owns modelsetup/moduletool/docs. QA independently reviews without implementation edits.

Use existing locks and model decisions. Actual model/tokenizer/ALM versions, full real100k pipeline, recovery promotion and other platform deployment remain NOT VERIFIED until operator evidence. HTTPS requirements in earlier guides are historical defaults superseded only by explicitly selected intranet mode.
