# M5 operations runbook

화면별 한국어 사용법: [웹 UI 사용 설명서](../../WEB_UI_GUIDE.ko.md).

Use an HTTPS reverse proxy matching ALMRAG_ALLOWED_ORIGIN for administrator Secure-cookie sessions. Default local Compose HTTP health is a development boot check. Do not weaken CSRF, origin, Secure-cookie or project ACL to make a local UI test pass. API keys stay in browser memory; project grants determine actions, while global backup/recovery requires an administrator session.

Register source_type first, then discover Codebeamer Project/Tracker or Polarion Project/Work Item Type. Select scopes and fields, save rate policy, run preflight, and SYNC with its config_revision. Changing selection invalidates readiness. Independent COLLECT/PROCESS/EMBED/INDEX and EXPORT/IMPORT use durable FIFO stages. Diagnostics include success and failure; replay/retry/resume require project_manage, failed list requires project_read.

Export a project to an opaque artifact reference; download authorized ZIP. Import requires matching canonical project/instance identity, validated checksums and MERGE_ONLY. Duplicate is no-op, conflicting same revision is quarantined, missing Items never delete existing data. Import remains inactive until explicit processing/embedding/index publication. Source latest pointers are preserved, not inferred from revision ordering. Actual ALM is unnecessary for offline imported inputs.

Create manual or scheduled backups as an administrator; inspect the raw-only manifest. Prepare restore to receive an actor/manifest-bound expiring one-use nonce. Restore creates a new isolated recovery directory, returns RAW_ONLY_REBUILD_REQUIRED and REREGISTRATION_REQUIRED, and does not replace live storage. Re-register authentication locally and reprocess/embed/reindex before separately planned promotion. No destructive restore or production promotion was tested or authorized.

Git remains source of truth. Summary outbox accepts only milestone/commit/SRS/count fields. Notion provider and automatic maintenance delivery are opt-in and disabled by default; configure an env/vault secret reference only after separate destination/transmission approval. Actual remote publication remains NOT VERIFIED.
