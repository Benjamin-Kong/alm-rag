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

## M2 approval and M3 start — 2026-10-20

After delivery of M2 commit0b38393 and its completion report, including the initial-profile TDD chronology exception and retained live/platform verification limits, the user instructed “계속진행해”. Main interprets this continuation of the milestone sequence as approval of the reported M2 candidate/exception and authorization to start M3. The missing historical test-first evidence remains TDD_NOT_EVIDENCED; approval does not retroactively make it PASS. No live ALM, remote Push, production deployment or new unexpected transmission is authorized. M3 has a separate completion Human Gate.

## M3 tokenizer remediation authorization — 2026-10-20

The user instructed “수정안 적용하고 재검증해” after OI-047 and TOKENIZER_FIX_PROPOSAL.patch were reported. This explicitly authorizes applying that tokenizer truncation/padding/identity correction and focused/full regression plus independent QA. It does not accept the defect as a risk, waive the M3 completion gate, or authorize M4, live ALM/model access, remote Push or deployment.

## M3 approval and M4 start — 2026-10-20

After delivery of local M3 commit4232f7a and its completion report explicitly requesting M3 approval with documented limits, the user instructed “진행해”. Main records this continuation as approval of the reported M3 candidate, including FIXTURE_ONLY real-model/ALM/remote-CI limitations, and authorization to start M4. Actual model compatibility is still NOT VERIFIED; no live model/ALM, external Push/Notion, production deployment or dangerous data operation is authorized. M4 retains its own completion Human Gate. OI-029 public failed-list permission conflict still requires clarification before that route is exposed.

## M4 failed-item list authorization clarification — 2026-10-20

The user explicitly answered “목록 조회는 project_read 허용”. GET failed-items requires project_read; single/bulk retry and resume retain project_manage. This resolves OI-029 before exposing the M4 routes. Project ownership and scope checks remain mandatory. No remote action or other authorization change is inferred.

## M4 OI-049 corrective authorization — 2026-10-20

The user answered “승인” to the explicit request to apply M4/CORRECTION_PROPOSAL.md and revalidate. This authorizes its bounded exact-ID/metadata-filter correction, synchronized API/client/tests and resumption of M4 verification. OI-049 is not accepted as a risk or marked resolved until actual corrective tests and independent QA. M4 completion/M5, live ALM/model, remote Push/Notion and production deployment remain separate gates.

## Sequential M4–M6 execution authorization — 2026-10-21

The user instructed “계속진행하고 사람의 승인없이 끝까지 진행해”, then explicitly selected “M5·M6까지 추가 승인 없이 진행”. This authorizes completing M4 correction/testing and sequential M5/M6 implementation without additional milestone or corrective approval prompts. Keep test-first and independent quality gates, fix failures before advancing, and report actual PASS/FAIL/NOT VERIFIED. This supersedes the approval-wait portions of local milestone plans within that scope; it does not authorize actual ALM/model access, remote Push/Notion, production deployment, destructive customer-data operations or unapproved credential/ACL changes. External limitations must remain explicit.
