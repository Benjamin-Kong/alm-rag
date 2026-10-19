# Codex Multi-Agent — Environment Preflight Checklist

**Stage:** Preparation ONLY. v0.3 spec baseline conditionally approved; M1 coding requires a new direct start instruction.

## Planned configuration
- Main Coordinator uses repo-root `AGENTS.md`; 6 configured subagent roles in `.codex/agents/`.
- Roles: `requirements`, `architect`, `alm_collector`, `rag_engineer`, `frontend`, `qa`.
- `.codex/config.toml`: `approval_policy = "on-request"`; `sandbox_mode = "workspace-write"`; `[features] multi_agent = true`; `[agents] enabled=true; max_concurrent_threads_per_session=3`.
- Three is the maximum number of concurrent *subagent* threads, not the number of specialist role declarations.
- Worktree isolation is a workflow policy **not** a property automatically guaranteed by subagent spawning. Explicit worktree/branch assignment is mandatory for parallel edits.

## User machine verification procedure

Observed local results are recorded in `docs/review/CODEX_PREFLIGHT_REPORT.md`.
1. Install/update Codex for the chosen OS. Run `codex --version` and check version-specific config documentation.
2. Enter the extracted repository root, verify `.codex/config.toml` and all six role files are readable. Run `python tools/validate_baseline.py`.
3. Launch Codex from the repo root and use the **environment preflight ONLY** prompt in `PROMPTS.md`. Check it recognizes `AGENTS.md`.
4. Ask Main Agent to list six specialist roles, then perform *read-only* document review delegation with at most 3 concurrently.
5. Confirm approval prompts/sandbox permissions and Worktree approach using safe local-only operations; do not start M1 code.
6. Capture version, observed PASS/FAIL/NOT VERIFIED, screenshots/log identifiers without tokens or ALM content, in `docs/review/CODEX_PREFLIGHT_REPORT.md` once exercised on the target machine.

## Sources
- https://developers.openai.com/codex/config-reference
- https://developers.openai.com/codex/multi-agent

## Current environment results
- The following container observations are historical. For local-machine results and remediation, see `docs/review/CODEX_PREFLIGHT_REPORT.md`.
- Git 2.47.3 present and local repository initialized.
- Codex CLI executable not present in this ChatGPT container.
- GitHub CLI executable not present in this ChatGPT container.
- Six TOML roles and base multi-agent configuration verified statically, **not spawned/executed**.

## Local validation environment (2026-10-19)

Use a project virtual environment; the system `/usr/bin/python3` is 3.9 and cannot run this validator's `tomllib` import. Python 3.12 is the deployment draft baseline. From the repository root:

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r tools/requirements.preflight.txt
source .venv/bin/activate
export PATH="/opt/homebrew/opt/node@22/bin:$PATH"
python3 tools/validate_baseline.py
```

The environment has already been created on this machine; do not recreate it on each run. Activate it and run the validator. `.venv/` is ignored by Git. This pin is for the documentation validator only, not an M1 application lockfile.

Local Docker tooling is provided by Homebrew Docker, standalone `docker-compose`, and the dedicated Colima profile `alm-rag`. No global Node relinking or shell profile modification is required. The VM has no host-directory mounts and does not replace the default Docker context:

```sh
colima start alm-rag --cpu 2 --memory 2 --disk 20 --mount none --activate=false --ssh-config=false
docker --context colima-alm-rag version
docker-compose -f deploy/compose.yaml config --quiet
colima stop alm-rag
```

VM commands require host permissions. Use the standalone `docker-compose` command unless the Docker CLI plugin directory has separately been configured. Compose config validation does not build or start the application. Future application bind mounts must be configured explicitly in M1; this minimal VM profile is for environment verification.
