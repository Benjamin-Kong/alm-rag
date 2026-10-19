# ADR-001 — SQLite source of truth, Qdrant disposable index
Status: Proposed for final approval

Context: ALM Item revisions and attachments require lossless persistence. Search requires dense+keyword retrieval and project filtering.
Decision: SQLite stores normalized and raw Item revisions, selection, credentials references, job state and active index/revision registry; Qdrant is replaceable search index. Keyword engine choice (SQLite FTS5 vs Qdrant Sparse) remains a measured design detail.
Consequences: Cross-store consistency and publication workflow require explicit staging/validation and crash-recovery tests. Primary backup includes SQLite plus attachment store. Rebuild index from originals is available.
Trace: Q04,Q06,Q07,Q22,Q24,Q25,Q28.
