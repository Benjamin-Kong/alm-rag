# M3 Main actual TDD evidence — 2026-10-20

Synthetic fixtures only. These results do not establish a real model/tokenizer calibration or full milestone acceptance.

- embedding.py: missing-module collection Red exit2 before implementation; initial8 tests Green. Digest/tokenizer count/vector mismatches, no live network by default, fixture trust boundary, exact-input limit, pinned local artifact/special tokens, sanitized model failures.
- model_runtime.py/settings: actual3FAIL before registry/settings → combined runtime+embedding11PASS0.26s. No artifact download, config cannot claim verified, per-job client callbacks isolated.
- API/Worker/CLI: tests/test_m3_api.py and test_m3_worker_cli.py first6FAIL1.04s (missing routes/dispatch/commands) → Green. Processing contract typed-results first1FAIL($ref missing) → typed models → targeted API/CLI/security17PASS3.03s.
- Normalizer resource safety: test_parser_resource_limit_never_accepts_empty_recovered_document first1FAIL0.06s → reject parser FATAL/resource errors → integrated45PASS5.75s. Independent QA reproduced300deep and10,000,001character cases as Item-local HTML_PARSE_INCOMPLETE, normalizer+chunker49PASS0.12s.
- Frontend M3 typed processing methods: new test first1FAIL/3PASS(TypeError missing configureProcessing) → generated current M3 contract + methods → full8PASS; TypeScript/Vite build PASS.
- Main full regression before OI-047 regressions:264PASS21.05s. This did not cover the subsequent tokenizer flaw and is not final acceptance.
- OI-047 new regression tests: test_local_tokenizer_counts_full_unpadded_input, two parameter cases actually2FAIL0.18s. Artifact truncation gives8 vs2000 expected; artifact padding gives16 vs1 expected. Implementation stopped per AGENTS Major gate. Proposed patch is NOT applied, Green NOT RUN.

Specialist evidence: NORMALIZATION_TDD.md, CHUNKING_TDD.md, PROCESSING_TDD.md. Unfinished isolated mock-E2E tests first2FAIL due test assumptions; not integrated or claimed PASS. Full suite after adding the two known failing tokenizer tests has not been rerun.

## OI-047 authorized correction — 2026-10-20

User “수정안 적용하고 재검증해” authorized the saved proposal. Added a local WordLevel15,000-token chunk regression with simultaneous artifact truncation/padding, BOS preservation, independent untruncated tokenizer comparison, full character-span coverage, new tokenizer identity and original artifact checksum preservation. Before implementation: two existing cases +new case actually3FAIL0.59s. Applied exactly the saved no_truncation()/no_padding()/identity-version patch. Focused embedding+chunking+model-runtime+processing:62PASS6.35s. Full regression and independent QA results are recorded in TOKENIZER_REVALIDATION.md when complete. The earlier failure chronology above is retained as historical evidence.

Final correction revalidation: Main267PASS22.58s; Frontend8PASS/build; project Python3.12 DOC_STATIC_PASS42API; diff-check PASS. Independent focused43PASS1.72s plus separate long/padded-input repro, old identity rejection, changed profile fingerprint and model count mismatch checks PASS. OI-047 resolved within this tested local scope. No real model verification or overall M3 acceptance is inferred.
