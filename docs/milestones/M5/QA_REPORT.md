# M5 independent QA — 2026-10-21

Read-only QA role m4_core_qa. Root integration and packaging are attributed separately.

Independent backend regression: **464 PASS / 67.76s**, dedicated local real Qdrant, no SKIP. Independent frontend: **24 PASS / 7 files / 1.13s**, TypeScript and production build PASS (698ms). After the new JobInfo progress contract, independent target **11 PASS / 2.45s**. Root final browser7PASS and final Python run are reported in TEST_REPORT; final independent repeat is pending delivery and is not claimed here.

Original review confirmed four operations Majors: namespace poisoning, missing offline import inputs, long writer heartbeat starvation, ZIP writer/reader budget mismatch. Each had corrective tests and all four independent adversarial reproductions now pass. Independently forced worker terminal transition and replacement-completed stale ownership: own terminal accepted, stale owner LeaseLost preserved. Frontend review rechecked SOURCE-field resets, empty filter omission, owner-checked revision fallback,403/500 no fallback and HTML/SVG bounds. No remaining confirmed Critical/Major identified in the reviewed scope. QA made no implementation edits.

Root separately executed final API/worker roundtrip, wheel installation, container boot/smoke,24frontendunits/build and7realChromiummockE2E. Those are not described as independent packaging QA. Real ALM/model/Notion, full vector restore, production promotion/TLS deployment, remote CI and other host OS remain NOT VERIFIED. UI preview bound is 1,048,576 UTF-16 code units, not literal UTF-8 byte count. Historical M2 TDD exception is retained.
