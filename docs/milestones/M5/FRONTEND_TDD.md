# M5 frontend TDD evidence — 2026-10-21

Scope: SRS-025/029/044/045/046/047/053/056/057/058/059 and shared security/original-retention requirements. Synthetic fixtures only. Node 22 PATH is required. Root owns Playwright/config/dependencies and the public API contracts; this specialist owns the React implementation and bounded correction tests.

## Initial Red / Green

- 06:36:52: `npm --prefix frontend test -- --run src/console.test.tsx` **3 FAIL**. The foundation had no API-key connection form, explicit-project search, or permission-aware console.
- Implemented authenticated dashboard, stages/SYNC, product-first discovery wizard, search/explorer, failed-item replay, diagnostics, package/backup forms, audit and evaluation preparation. API keys/passwords are cleared from inputs after connection and never persisted. Generated M5 schemas back client operations. Administrator sessions use the existing readable CSRF cookie; no authentication/ACL policy was changed.
- 06:54:51: `npm --prefix frontend test` **13 PASS**, `npm --prefix frontend run build` **PASS**.
- 06:55:33: Explorer target **1 FAIL / 1 PASS**: Item detail 404 blocked viewing preserved, unpublished revisions. Implemented 404-only fallback to stored revision plus explicit unpublished state, complete escaped JSON and field-selected inert HTML preview. The first subsequent run found an ambiguous assertion because the same complete original appears in both raw and revision panels; changed the assertion to require both copies. This assertion failure was not an application success.
- Root subsequently completed explicit 1 MiB/10,000-node/100-depth preview refusal and pinned wizard preflight configuration. Those implementation/test details are recorded in root integration evidence; the specialist does not claim an unobserved root run.

## Independent QA correction round

Refreshed owned files from Main before applying changes, retaining root's preview refusal and configuration pinning. 08:33:55 targeted command:

```
npm --prefix frontend test -- --run src/console.test.tsx src/explorer.test.tsx src/wizard.test.tsx
```

Observed **5 FAIL / 5 PASS**, with distinct failing assertions:

1. SOURCE field `old-custom` survived changing projects and survived changing products (**2 FAIL**).
2. A blank metadata search submitted `filters:{}` (**1 FAIL**), causing unnecessary metadata enumeration and possible broad-filter rejection.
3. After opening project A's catalog, an unpublished search result belonging to B used the catalog's owner (**1 FAIL**).
4. SVG namespace `tagName` casing caused script/text subtree contents to be unwrapped rather than discarded (**1 FAIL**, no script execution observed).

Minimum corrections: reset selected embed fields to normalized Title/Description on every project/product switch; omit `filters` entirely when blank while preserving explicit nonempty ID/scope filters; pass the known owner from the catalog/search entry and validate authorized project + detail owner; normalize tag names before the structural allowlist/drop checks. HTML sources are parsed only inside an inert template; rendered React nodes carry no source URLs/event/style attributes. Whole active subtrees are discarded, table spans are restricted positive integers, and full originals remain escaped and complete independently of preview limits.

08:34:21 full unit regression **20 PASS**, TypeScript + production Vite build **PASS**. Added non-Red security regression checks proving detail 403 and 500 never fall back to revision text, plus nonempty-filter request assertions. 08:34:40 final:

```
export PATH="/opt/homebrew/opt/node@22/bin:$PATH"
npm --prefix frontend test
npm --prefix frontend run build
```

Observed **22 PASS / 5 test files**, **build PASS** (Vite 6.4.4, 36 modules). These two 403/500 checks passed on their first execution and are regression evidence, not fabricated Red evidence.

## Boundaries

- Component tests use jsdom and mocked fetch. They do not establish real browser or live-server success. Root independently owns and reports Playwright real Chromium tests.
- No actual ALM/model access, remote Notion publication, production deployment, Git push, or destructive restore was performed.
- Backup recovery wording explicitly requires index rebuild and credential re-registration; it does not claim active database restoration.
- The evaluation screen prepares query/relevant IDs only until M6 provides the metrics engine.
