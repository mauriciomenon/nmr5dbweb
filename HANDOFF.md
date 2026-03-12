# Handoff

## Current Context

This repo is being turned from a student fork into a product-owned repository.

The first stabilization slice is intentionally narrow:

1. persist architecture knowledge in repo MD files
2. remove versioned local/runtime state
3. avoid broad refactors

## What Was Confirmed

- Product working clone is `/Users/menon/git/nmr5dbweb`
- Student source is `allysonalmeidaa/mdb2sql_fork`
- Clone source branch was `minha-alteracao`
- Current local/product branch is `master`
- `origin`: `https://github.com/mauriciomenon/nmr5dbweb.git`
- `upstream`: `https://github.com/allysonalmeidaa/mdb2sql_fork.git`

## Risks To Remember

- `static/app.js` is still a large monolithic frontend file even after removing the six most critical duplicated functions
- Backend responsibilities are concentrated in one large Flask file
- Search and compare use different models and are hard to reason about together
- `tools/encontrar_registro_em_bds.py` still has heavy style debt even after the generic-search repair
- The Flask backend is now safer on upload/search/index paths, but the file still carries broader maintainability debt

## Setup Status

- Clean Python setup now uses `uv`
- Use `requirements.txt` for runtime
- Use `requirements-dev.txt` for runtime plus validation tools
- Project-local venv is now `/Users/menon/git/nmr5dbweb/.venv`
- Project-local Python is now `3.13.12`
- Focused compare and generic-search tests pass in the project-local venv
- `ruff` and `ty` still expose broad existing debt outside the setup slice
- This round removed six duplicated hot-path functions from `static/app.js`
- `node --check static/app.js` passes after the JS cleanup
- Avoid `uv run` in this repo for now; prefer direct `./.venv/bin/...` validation commands
- `tools/encontrar_registro_em_bds.py` now has `buscar_generico_em_tabela(...)` implemented and covered by focused tests
- Focused backend API validation is now green:
  - upload edge cases
  - index startup error paths
  - search parameter validation
  - compare and generic-search regressions
- No-key table compare in `interface/compare_dbs.py` now runs its diff summary in DuckDB SQL instead of materializing full table rows in Python
- Keyed compare in `interface/compare_dbs.py` now quotes table and column identifiers consistently
- `interface/compare_dbs.py` now validates missing tables, `key_columns`, and `compare_columns` before building SQL
- `/api/compare_db_rows` now rejects malformed `key_filter`, invalid `change_types`, and `changed_column` outside the resolved compare columns
- `/api/compare_db_rows` no longer truncates the compare result before backend filtering and pagination
- `row_limit` now behaves as page-size/output control in this route, which matches the current frontend payload
- `/api/compare_db_rows` now uses a dedicated SQL-backed paged compare engine instead of filtering and paginating in Python
- The route still preserves the same JSON contract expected by `static/compare_dbs.html`
- The two touched `tools/` scripts no longer emit the old `py_compile` escape warnings in this repo
- Current no-key compare semantics are still the old ones by design:
  - row order is ignored
  - duplicate-only differences are ignored
  - `row_count_a` and `row_count_b` still reflect raw row totals

## Operator Notes For Next Conversation

- Read `PROJECT_STRUCTURE.md` first
- Read `ROUND_STATUS.md` second
- Read `RECOVERY_BACKLOG.md` for deferred work
- Keep changes minimal and behavior-preserving
- Use the project-local `.venv` only; do not rely on `/Users/menon/git/.venv`
- Natural next slices are:
  - review whether no-key compare should remain duplicate-insensitive or evolve to multiset semantics
  - deeper backend debt reduction in `interface/app_flask_local_search.py`
  - expand compare API payload-type validation if external callers send non-string fields today
  - consolidate the two keyed compare engines in `interface/compare_dbs.py` if this area keeps growing
