# M2 collection design

## Data and transaction boundaries

Ordered transactional migrations preserve v1 and add v2 tables. Source profiles are discriminated (Codebeamer RESTv3 / Polarion RESTv1). Persist discovered project IDs and product-specific scope/config snapshots. New collection_failures accepts failures before a source Revision exists; never manufacture a successful revision. Separate membership/observation state represents OUT_OF_SCOPE/MISSING/UNAUTHORIZED without claiming deletion. Existing FailedItem/revisions remain intact.

Every collection outcome/failure/checkpoint/count update checks the Job fencing token in the same SQLite write transaction. A background heartbeat renews the job lease during network/waits. Losing a lease prevents subsequent requests and commits. Idempotent outcomes key by job+item; immutable revisions reuse same source revision+hash and reject conflicting content. M2 never changes active_revision_uid. Files use internal IDs/checksums and atomic rename, never user-supplied filenames as filesystem paths.

## Server protection

ALMHttpClient is the only connector-owned HTTP entry. GET is the default; only an explicitly verified exact wiki renderer POST is allowed. Reject credentials/query in configured base URLs, redirects, off-origin/out-of-profile paths, traversal and unsupported methods. Bound bytes/pages/attempts/elapsed retry budget. Never log URL query, headers or bodies. Live requests require explicit enablement and trusted origin configuration; test transports bypass only the socket requirement, not safety/rate rules.

SQLite stores a server-wide token bucket, minimum-start interval, pause and expiring inflight permits shared across credentials/processes. Credentials may further restrict but never expand server budget. Acquire/release in short transactions; never sleep/network while holding DB write lock. Every attempt—including discovery/attachment/render—obtains a permit. Retry-After seconds/date extends global pause and survives restart; a wait beyond remaining budget returns PAUSED rather than sending early. Bounded5xx/network retries use backoff+jitter. 401 blocks credentials globally;403/404 are isolated/ambiguous, never proof of deletion. Circuit-open stops globally.

Final refinements: canonical URL/origin uses HTTPX normalization, including host case/IDNA/default443/80, for profiles, budgets, allowlists, policy and lock paths. OS advisory slot ownership lasts through stream close; expired SQLite rows are reclaimed only when their stable slot lock is free. Never unlink active lockfiles. Abort callbacks may perform lease fencing and therefore run outside transport write transactions. Existing noncanonical prototype budget state fails closed pending separately reviewed migration. Logical deadlines reject late completion; no hard interruption claim for a blocked sync read.

## Connector interface

Connector(client, renderer_verified=False). probe()->dict; list_projects()->list[{id,name,url}]; list_scopes(project_id)->list[{id,name,kind}]; list_fields(project_id,scope_ids=None)->list[{id,name,...}]; iter_refs(project_id,scope_ids=None)->iterator[{id,scope_id,revision?,modified?}]; get_item(project_id,item_id)->normalized envelope; download_attachment(project_id,item_id,attachment)->bytes.

Envelope: id/project_id/scope_id/revision/modified/title, description{format,raw,html?}, fields[{source_field_id,name,source_format,raw_value}], complete raw payload, relations[{type,target_id}], attachments[{id,filename,path,source_url}], source_url and explicit deleted evidence if supported. No live auth/header state is serialized. Official links remain raw and are never crawled/mapped automatically.

Codebeamer Tracker ID is distinct from tracker type; Polarion Work Item Type is an enumeration classification. Pagination must be complete or fail globally, with repeated cursor/page protection. Selected IDs must be revalidated against current catalogs before collection; preflight pins scope/config fingerprint and estimates requests. M3 model/index checks are explicitly unavailable, so COLLECT readiness is distinct from full SYNC readiness.

Normalized title/description capabilities are separate from original readable_fields catalog IDs. Source scope/tracker participates in field definition identity; legacy definitions/revisions are never rewritten. Preflight also fingerprints the reviewed rate policy. Request total remains explicitly UNKNOWN because pages/attachments/retries are not known; mandatory Item detail calls provide only a lower bound. Pure per-Item field/description/relation conversion errors are locally queued; identity/catalog/pagination/network/global control failures retain their safety boundary.

## Contract and approval limits

Global source administration uses admin sessions; project collection uses existing project_manage grants and read diagnostics use project_read. No existing grant is widened. Public failure-list/replay endpoints stay unimplemented pending OI-029. New API payload/response schemas, authorization tests and generated client accompany implementation. Real API version compatibility, actual wiki rendering side effects and production server rate limits remain NOT VERIFIED.

Official reference pages are read for candidate profiles; their existence is not proof of a server's enabled API or permissions. Exact fixtures and assumptions are recorded by the connector specialist.
