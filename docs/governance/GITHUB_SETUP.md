# Private GitHub remote — setup runbook

**Current status:** Local Git initial commit and conditional-baseline tag created. No remote repository exists in this preparation environment; no remote push performed.

## Recommended GitHub settings
- Repository: `alm-rag` or another user-selected name; **Private**, no public visibility.
- Owner: user account or approved organization, confirmed by the user.
- `main` default branch, require PR review/status checks for protected branch where plan supports it; forbid force push/deletion.
- No customer ALM data/attachments/dumps, credentials or generated operational logs in GitHub/Notion. Check `git status`, staged diff, `git ls-files` and secret scan **before first Push**.
- Do not use `--public`, `--push` during repository creation until explicit push confirmation.

## Existing local commit
The archive contains `.git` and tag `baseline-v0.3-conditional`. Extract archive and open `alm-rag` folder. Confirm with:

```bash
git status --short
git log -1 --oneline
git tag --list
python tools/validate_baseline.py
```

## After GitHub access is established and user authorizes remote creation/Push
In a machine with GitHub CLI (`gh`) and authenticated GitHub access, choose the appropriate OWNER; creating under the user's own account:

```bash
gh auth status
gh repo create alm-rag --private --source=. --remote=origin
gh repo view --json visibility,nameWithOwner,url
# Check exactly PRIVATE before push; audit tracked files/secrets.
git status --short
git ls-files
# Obtain explicit approval for the destination/initial Push before running:
git push -u origin main
git push origin baseline-v0.3-conditional
```

Alternative: create a PRIVATE empty repository in GitHub UI, then use `git remote add origin <EXACT_USER_REPO_URL>` (never invent URL), verify visibility and Push only when authorized.

## GitHub access constraint
This ChatGPT environment did not expose an authenticated GitHub repository tool or `gh`; it cannot create the remote or Push for the user. The repository ZIP/Git bundle allows continuation on the user's authenticated PC/Codex environment.
