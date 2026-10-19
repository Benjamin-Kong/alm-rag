# ALM RAG v0.3 — Conditional Baseline Approval

- **Approval date:** 2026-10-19 (Asia/Seoul)
- **Authority:** Explicit user decision in the ALM RAG requirements discussion
- **Status:** `CONDITIONALLY_APPROVED_FOR_ENVIRONMENT_PREPARATION`
- **Baseline content:** Q01~Q50 final decisions, SRS-001~059, SRS/SAD/OpenAPI drafts, requirements + test traceability, TDD, Codebeamer/Polarion connector specs, 6 specialist Codex roles and M1~M6 gates.

## Conditions carried forward without changing policy
1. Legacy REQ-001~252 clause text was not available in the v0.3 package. Preserve OI-019, OI-023 as `NOT VERIFIED`; do not treat numbering/mapping as clause-level proof. Nine IDs (REQ-001 and REQ-003~010) had no direct number link in decision summaries.
2. OpenAPI response detail, SQLite/Qdrant consistency, real ALM API compatibility, Docker build and runtime are not yet tested. Keep existing open-issue status and phase gates.
3. Authorized in this stage: Git LOCAL initialization/initial commit; documentation and Codex role setup/preflight; safe validation scripts.
4. Not authorized/NOT requested yet: M1 application coding, remote GitHub repository creation if no connection, GitHub Push without separately confirmed destination/permissions, live customer ALM access or data upload.
5. Source of truth for docs/code will be Git; Notion holds sanitized summaries and approval records, not ALM records or secrets.
6. `baseline-v0.3-conditional` is a **document baseline tag**, not a release, nor evidence of runnable application.

## Human Gate
After Codex setup and remote repository configuration, user must explicitly instruct `Start M1` before developers or agents write application code. M1 QA approval will be a separate decision before M2.

## Subsequent M1 start authorization — 2026-10-19

The user instructed “커밋반영하고 착수해” after environment remediation. This authorizes the local preparation commit and M1 implementation. It does not approve M1 completion, M2, GitHub Push, deployment or live ALM access. See `docs/milestones/M1/PLAN.md`.
