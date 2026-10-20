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

## M1 approval and M2 start — 2026-10-20

The user instructed “M1승인. 다음 단계를 진행해”. M1 commit `13e1f30` and its documented limitations are approved; M2 is authorized. No remote Push, deployment or live customer ALM access is inferred. M2 must stop at its own Human Gate.

## M2 transport remediation authorization — 2026-10-20

The user instructed “수정안을 적용하고 계속진행해” after reviewing M2/COMPLETION.md. This authorizes the proposed OI-035/036/037 corrective work, regression tests and resumption of M2. It does not accept the defects as risks or waive the AGENTS.md stop rule for newly discovered unresolved Major issues. M2 completion/M3, remote Push, deployment and live ALM remain separate gates.

## M2 Item isolation and integration remediation authorization — 2026-10-20

The user instructed “보완하고 계속 진행해” after the OI-038 Major and associated integration findings were reported. This authorizes the concrete OI-038/039/040/041 corrections described in M2/COMPLETION.md, completion of M2 REST/CLI/contracts/worker/mock acceptance and independent QA. It does not authorize M3, live ALM, remote Push or deployment, nor accept known failures as passed. M2 resumes IN_PROGRESS and retains its completion Human Gate.

## Continued M2 corrective implementation — 2026-10-20

After the next independent QA checkpoint identified equivalent-origin/default-port budget separation and the Worker attachment-directory mismatch, the user instructed “진행중인가? 계속 구현해”. Main announced these two concrete remaining corrections and continued their regression-first implementation within M2. Record them as OI-042/043; do not accept the initial QA FAIL as passed or waive the M2 completion gate. No external action or requirements change is authorized.
