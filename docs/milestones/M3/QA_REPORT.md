# M3 independent QA checkpoint — 2026-10-20

Current status: OI-047 correction PASS within the local tested scope after user authorization. The final M3 local candidate is now PENDING_HUMAN_APPROVAL; it is not an approved milestone or full product acceptance. The original FAIL checkpoint and repro evidence below remain historical. See TOKENIZER_REVALIDATION.md for current results. Reviewer roles m3_normalize_review and m3_full_qa did not modify implementation.

## OI-046 — Major, RESOLVED within tested scope

lxml recover=True accepted FATAL ERR_RESOURCE_LIMIT as a warning. A normal paragraph followed by300nested divs and a tail paragraph yielded only the prefix; >10MB text likewise disappeared from derived output. Raw M2 envelope remained intact. Root actual regression1FAIL then rejects FATAL/resource/invalid encoding/character parse errors as Item-local HTML_PARSE_INCOMPLETE. Independent re-execution of both resource repros confirmed rejection and49normalizer/chunker tests PASS. No remaining issue in that reviewed scope.

## OI-047 — Major, RESOLVED within local tested scope

LocalTokenizer loads tokenizer.json defaults without disabling serialized truncation/padding. Independently reproduced WordLevel artifact with truncation max8:2000 source tokens counted8; make_chunks emitted one chunk recorded8 while actual complete input had2008 tokens, exceeding1024. Short calibration strings still matched3 and7, so current short probes alone do not establish long-input exactness. Paddinglength32 counted32 for one actual token. Root new regression2FAIL independently confirms8/2000 and16/1.

This violates SRS-013/048 exact-input chunk accounting. Ollama truncate:false plus returned token-count checking mitigates accepting a silently truncated embedding; no source-envelope loss or accepted truncated vector was demonstrated. Functional token-bound correctness still requires correction before proceeding.

Originally proposed and now applied: TOKENIZER_FIX_PROPOSAL.patch loads pinned artifact, then no_truncation()/no_padding(), with a new tokenizer processing identity so old profiles/caches cannot silently retain old semantics. Preserve special tokens and source artifact checksum. Required verification: existing two Red regressions → Green, long-input chunk bound with local exact tokenizer, runtime calibration special tokens/count mismatch, full regression and independent QA. No model weights/download or live ALM required.

## Other observed evidence and boundaries

Initial independent full run262PASS/2FAIL20.83s identified in-progress contract snapshot/typedresponse gaps. Root regenerated typed schemas/current snapshot and Main subsequently264PASS21.05s. Those runs preceded the new OI-047 regressions; do not call the current tree all-green. Project-scoped caching, revision ownership triggers, source/config/model pinning and lease-fenced writes have local synthetic tests. Review originally stopped on OI-047. The authorized correction passed focused independent QA; no overall M3 acceptance signoff.

NOT VERIFIED: real Ollama digest/context/tokenizer match, actual customer ALM, real vector quality, Qdrant publication/M4, new M3 container build/boot, wheel isolated install, full-platform matrix, remote CI, operational UI and full milestone traceability. No authentication/ACL policy expansion or remote action was performed.


## Authorized correction round1 final independent result

m3_tokenizer_retest independently ran43embedding/chunking/runtime tests and26processing/API/CLI/Worker tests:PASS, with no file modifications. Original2001→8truncation and32→2padding repros corrected; exact chunks now5/max725, sourcechecksum/BOS retained, oldidentity/profile/cachedvector namespace separated, servercountmismatch rejected. No Critical/Major remains in this bounded correction. M3 overall completion is still not reviewed/approved.

## Final M3 local gate QA — 2026-10-20 (latest)

Reviewer m3_final_gate_qa performed read-only review after integration. Actual `.venv/bin/pytest -q`: **271PASS33.18s**; project-runtime DOC_STATIC_PASS and diff-check PASS. No confirmed remaining Critical/Major found within reviewed scope. Reviewed project-cache/revision ownership, fenced writes/partial resume, API ACL, unverified-model blocking,15k+100row coverage,100/3parser isolation and no active/index publication. Independent requirement reviewer verified exact10Primary+7Shared assignments and identified documentation/CI parity updates, now reflected in M3_TRACEABILITY.csv/GATE_MATRIX.md/current CI paths.

TEST-044..059: inherited M2 discovery/transport/auth regressions retained; M3 exact-input/table/retention and per-Item isolation PASS in local fixtures. M5 wizard/UI, public replay/M4 active search/publication, real ALM/model/tokenizer/context, hard process kill during real-model I/O, remote CI remain NOT VERIFIED. Container/wheel evidence is Main-measured and was not independently rerun by this QA agent. Frontend8tests/build are Main-measured. Static-system-Python tomllib failure is retained as environment limitation; project Python3.12 passed.

The final local candidate is **PENDING_HUMAN_APPROVAL**, not a production release. No unresolved code Major/Critical was identified. Real-model verification is absent and is an explicit milestone limitation for user review, not a fabricated PASS. Earlier checkpoints/failures remain in this file and the TDD records. M3 runtime, original-source compatibility and later-stage acceptance limitations cannot be waived by QA.
