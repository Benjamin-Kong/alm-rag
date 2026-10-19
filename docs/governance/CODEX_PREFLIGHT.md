# Codex Multi-Agent — Environment Preflight Checklist

**Stage:** Preparation ONLY. v0.3 spec baseline conditionally approved; M1 coding requires a new direct start instruction.

## Planned configuration
- Main Coordinator uses repo-root `AGENTS.md`; 6 configured subagent roles in `.codex/agents/`.
- Roles: `requirements`, `architect`, `alm_collector`, `rag_engineer`, `frontend`, `qa`.
- `.codex/config.toml`: `approval_policy = "on-request"`; `sandbox_mode = "workspace-write"`; `[features] multi_agent = true`; `[agents] enabled=true; max_concurrent_threads_per_session=3`.
- Three is the maximum number of concurrent *subagent* threads, not the number of specialist role declarations.
- Worktree isolation is a workflow policy **not** a property automatically guaranteed by subagent spawning. Explicit worktree/branch assignment is mandatory for parallel edits.

## User machine verification (NOT YET RUN HERE)
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
- Git 2.47.3 present and local repository initialized.
- Codex CLI executable not present in this ChatGPT container.
- GitHub CLI executable not present in this ChatGPT container.
- Six TOML roles and base multi-agent configuration verified statically, **not spawned/executed**.
