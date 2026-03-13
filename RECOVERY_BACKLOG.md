# Recovery Backlog

## Purpose

Track real product debt that should not be fixed in the current slice.

## Open Items

1. Break `interface/app_flask_local_search.py` into smaller backend units without changing behavior.
2. Continue shrinking the new search frontend modules (`static/app.js`, `static/app_search.js`, `static/app_bootstrap.js`) only where there is a measured maintenance or bug-risk gain.
3. Decide whether compare-without-key should remain duplicate-insensitive or move to true multiset semantics.
4. Define one clear contract for DuckDB usage:
   - SQL compare
   - `_fulltext` search index
   - Access fallback
5. Normalize docs and naming to the product repo identity instead of the student fork.
6. Continue reducing style and maintainability debt in `tools/encontrar_registro_em_bds.py` after the generic search flow repair.
7. Formalize the `uv` workflow with stronger project metadata or lockfile support, so the repo no longer depends on direct `./.venv/bin/...` discipline.
8. Review tool scripts and notes for machine-specific leftovers before each release.
9. Expand compare endpoint validation for non-string payload fields if external callers are sending mixed JSON types in practice.
10. Continue reducing the remaining page-specific CSS duplication now that `static/index.html`, `static/track_record.html`, and `static/admin.html` all use the shared shell/component layer.
11. Continue shrinking the compare frontend modules (`static/compare_dbs.js`, `static/compare_dbs_render.js`) after the current operator flow stabilizes.
12. Keep expanding browser regression on top of the now broader full-UI suite:
   - admin drag-and-drop priority reorder assertions
   - compare export assertions by isolated change-type modes
   - track directory modal upward-navigation assertions
   - environment strategy for Playwright browser bootstrap
13. Keep hardening the SQLite contract across the main Flask UI/backend flow:
   - explicit status messaging in the UI
   - predictable table browsing behavior
   - no accidental DuckDB fallback when the active file is really SQLite
   - evaluate whether SQLite search should gain its own lighter index path later
14. Add a richer report layer for database differences, based on real anomaly-reading needs, while preserving the current fast keyed compare path unchanged.
15. Review whether the browser regression should manage its own Playwright browser bootstrap or stay environment-driven.
16. Continue reducing the backend global-state concentration in `interface/app_flask_local_search.py` now that startup/runtime DB handling and active-DB resolution are safer.
17. Review whether the JS lint baseline should be tightened in phases after the current legacy global-script model is reduced.
18. Continue cleanup by proof of use only:
   - review old docs and references before removal
   - keep backups in `bkp_limpeza/` until explicitly discarded
19. Continue breaking down `interface/app_flask_local_search.py` by functional islands after the admin upload block:
   - search/table browsing
   - record tracking flow
   - startup/config persistence boundaries
20. Continue reducing duplication inside the actual browse/search implementations in `interface/app_flask_local_search.py` after the current helper extraction:
   - keep the DuckDB fast path intact
   - avoid broad engine abstraction layers
   - keep row serialization and result ordering behavior stable
21. If `output/` grows further, define retention rules so the local validation area does not become an unbounded dump of operator samples.
22. Reassess the legacy `.eslintrc.cjs` fallback only after external analyzers stop depending on old `ESLint 8.x` behavior.
23. If the real operator datasets keep exposing the same column families, consider making the frontend column-priority list configurable instead of hard-coded.
24. Reassess whether the operator preview cards in the search screen should become collapsible when datasets with many short tables dominate usage.
25. Access `.accdb` conversion still depends on local driver/runtime setup in this environment:
   - `pyodbc` package in uv env
   - compatible Access ODBC driver
   - optional `mdbtools` path for `.mdb`
26. Decide if `artifacts/validation/derived/` should stay local-only forever or gain a curated tiny committed fixture subset for CI.
27. Add a dedicated compare-browser smoke for report export payload quality per filter mode (`changed`, `added`, `removed`), not only combined mode.

## Do Not Pull Into Slice 1

- Large refactors
- UI layout changes
- New product flows
- Performance rewrites without measured evidence
