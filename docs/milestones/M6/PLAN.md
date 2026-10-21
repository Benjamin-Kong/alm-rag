# M6 plan — QUALITY_VERIFIED_WITH_DOCUMENTED_LIMITATIONS, 2026-10-21

M5 commit3731374 local quality verified:466Python,24frontend,7actualChromium/mockAPI, independent backend/frontend review, local Docker/wheel. User explicitly approved M5/M6 without further milestone/corrective prompts. External restrictions remain.

Primary10:033/034/035/036/037/039/041/043/058/059. Shared3:038/051/052. Use authoritative TRACEABILITY, no unrecovered legacy clause invention.

Root owns quality REST/CLI/worker integration, evaluation UI/client/schema, final evidence/CI/packaging. RAG specialist owns quality.py, retrieval method comparison,009 quality migration and tests/test_quality*.py in isolated .worktrees/m6-quality-engine. Bounded scale specialist will own tools/benchmark_m6.py, tools/benchmark_embedding.py and benchmark tests in a separate worktree. QA remains read-only, at most3 concurrent threads including root; no file conflicts.

Design→actual SRS-linked Reds→minimum implementation→unit/integration/mock E2E→independent QA and at most3 corrections/retest cycles. Persist integrity/evaluation reports, authorize all references before query, no arbitrary URL/path fetch. Golden Item-level P@K/R@K/MRR for dense/keyword/hybrid. Measure actual synthetic100k SQLite/Qdrant scale, capacity and chunk distribution; separate fixture embedding from real model performance.

Actual model artifacts/Ollama/ALM are unavailable and live access is not authorized. Do not fabricate model quality, calibration, CPU/GPU/remote throughput or warm-Ollama P95. Implement safe measurable harnesses and mark unavailable cases NOT VERIFIED. Other host OS/remoteCI/OS scan also NOT VERIFIED unless actually exercised. Final local commit/report, no Push/Notion/production deployment.
