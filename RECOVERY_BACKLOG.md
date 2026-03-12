# Recovery Backlog

## Purpose

Track real product debt that should not be fixed in the current slice.

## Open Items

1. Break `interface/app_flask_local_search.py` into smaller backend units without changing behavior.
2. Split `static/app.js` by responsibility now that the duplicated search/priority/bootstrap path has been removed.
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
11. Split `static/compare_dbs.js` into smaller page modules after the current compare operator flow stabilizes.
12. Add real browser-based UI regression checks once Playwright Chromium is available on this machine.

## Do Not Pull Into Slice 1

- Large refactors
- UI layout changes
- New product flows
- Performance rewrites without measured evidence
