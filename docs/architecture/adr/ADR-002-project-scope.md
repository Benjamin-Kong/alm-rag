# ADR-002 — Global Item identity and project-restricted retrieval
Status: Proposed for final approval

Context: ALM instance names, project names, source IDs, and Work Item types overlap.
Decision: Stable composite project UID + source-specific container semantics. All retrieval, fusion, de-dup and full Item hydration enforce authorized project UID list; absence of selector does not default to global search.
Consequences: Store project payload index and admin controlled API key scopes; avoid leaking references to foreign projects.
Trace: Q01,Q08,Q09,Q27,Q33,Q34.
