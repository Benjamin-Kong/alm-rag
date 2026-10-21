# GitHub remote / Push runbook

## Verified target and authorization — 2026-10-21

- Remote: `origin` → `https://github.com/Benjamin-Kong/alm-rag.git`
- Repository: PRIVATE, default branch `main` (verified with authenticated GitHub CLI).
- User explicitly instructed “원격 push가지 진행해”, authorizing Push of the completed current development branch `codex/m6-quality`.
- This branch includes M1..M6 local commits through ancestry. No force Push or remote branch deletion is needed.
- Source/data restrictions remain: no customer ALM records, attachments, credentials or production logs. This authorization does not enable actual ALM/model, remote Notion publishing or production deployment.

## Checks and commands

From the repository root:

```sh
git status --short --branch
gh repo view Benjamin-Kong/alm-rag --json nameWithOwner,isPrivate,url,defaultBranchRef
gitleaks git . --log-opts=HEAD --redact --no-banner
git push -u origin HEAD:refs/heads/codex/m6-quality
git ls-remote --heads origin refs/heads/codex/m6-quality
```

Compare the remote branch SHA with `git rev-parse HEAD`. Preserve local changes; do not resolve a non-fast-forward rejection with force Push. Inspect remote history before deciding how to reconcile it. The document tag `baseline-v0.3-conditional` is not an application release and is not automatically published by the branch command above.

GitHub Actions runs on Push according to `.github/workflows/m1.yml`. A successful Git Push is not evidence that the remote CI run passed; inspect its actual status separately.

## Recorded pre-Push evidence

At implementation commit0d8be0d the working tree was clean. gitleaks8.30.1 scanned10reachablecommits/~3.02MB with0leaks. The later documentation commit adds the Korean execution guide and this authorization record; the final reachable history is rescanned before Push. No scan output containing secrets is published.

The v0.3 preparation-only gate and later implementation approvals are historical records in BASELINE_APPROVAL.md. Current M6 quality evidence and remaining NOT VERIFIED items are in docs/milestones/M6/.
