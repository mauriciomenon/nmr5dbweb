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
12. Turn the manual Playwright browser pass into a repeatable regression check once the desired coverage and artifact policy are defined.
13. Consider adding focused frontend regression checks for the invalid-state flows now validated manually:
   - search without active DB
   - admin index start without DB
   - compare without A/B paths
   - tracking without required filters

## Do Not Pull Into Slice 1

- Large refactors
- UI layout changes
- New product flows
- Performance rewrites without measured evidence
