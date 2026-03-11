# Recovery Backlog

## Purpose

Track real product debt that should not be fixed in the current slice.

## Open Items

1. Break `interface/app_flask_local_search.py` into smaller backend units without changing behavior.
2. Remove duplicated function blocks from `static/app.js` and restore a single source of truth for UI actions.
3. Rework compare-without-key flow to avoid pulling whole tables into Python sets for large DBs.
4. Define one clear contract for DuckDB usage:
   - SQL compare
   - `_fulltext` search index
   - Access fallback
5. Normalize docs and naming to the product repo identity instead of the student fork.
6. Fix the broken code paths in `tools/encontrar_registro_em_bds.py`.
7. Restore a reproducible test environment so `pytest` runs without manual local repair.
8. Review tool scripts and notes for machine-specific leftovers before each release.

## Do Not Pull Into Slice 1

- Large refactors
- UI layout changes
- New product flows
- Performance rewrites without measured evidence
