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
- Current development branch is `codex/dev`
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
- The two keyed compare entry points in `interface/compare_dbs.py` now share the same internal validation, SQL-plan, and row-mapping helpers
- The route still preserves the same JSON contract expected by `static/compare_dbs.html`
- `static/index.html`, `static/admin.html`, `static/compare_dbs.html`, and `static/track_record.html` were reorganized around task-oriented navigation and clearer information hierarchy
- The page refresh preserved the existing DOM ids expected by `static/app.js` and the inline page scripts
- `static/shell.css` and `static/shell.js` now centralize the shared web shell/theme behavior used by the static pages
- The repeated inline theme/options blocks were removed from the page HTML files
- `static/shell.css` now also owns the shared search/track body and header shell base, so `static/index.html` and `static/track_record.html` no longer duplicate that layer inline
- `static/shell.css` now also carries a shared component layer for search/compare/track:
  - tabs and options menu
  - flow hints
  - compare/track form and workflow primitives
  - shared search/compare button styles
- `static/admin.html` now also sits on the same shared component layer for buttons, cards, form controls, status blocks, and responsive workbench layout
- `static/compare_dbs.html` now groups the operator flow into clearer compare panels instead of one long flat form
- `static/compare_dbs.html` now reuses shared request helpers for compare, pagination, export, tables overview, and restored state
- `static/compare_dbs.html` no longer carries the large inline page script; that logic now lives in `static/compare_dbs.js`
- Flask now serves the dedicated `/compare_dbs.js` asset successfully in local smoke validation
- `static/app.js` now has one active bootstrap path for search/admin and no longer carries the old duplicated copies of the search and priority handlers
- `static/app.js` is now split into:
  - `static/app.js`
  - `static/app_search.js`
  - `static/app_bootstrap.js`
- `static/compare_dbs.js` is now split into:
  - `static/compare_dbs.js`
  - `static/compare_dbs_render.js`
- Real browser validation has now been executed with Playwright on:
  - `/`
  - `/compare_dbs`
  - `/track_record`
  - `/admin.html`
- The admin page no longer requests `/api/tables` when there is no active DB selected
- The admin page also no longer attempts to start indexing from an obviously invalid no-DB state
- The search modal, compare flow, and tracking flow now prefer inline status messaging over alert-driven validation in the most common invalid states
- Compare actions now disable their own buttons while requests are in flight for load/export/overview paths
- Browser validation found only one non-blocking asset issue on the main page:
  - missing `favicon.ico`
- Product direction explicitly confirmed:
  - keep `DuckDB`, `SQLite`, and `Access (.mdb/.accdb)` support
  - preserve the current fast compare flow as the main operational compare
  - any future deep report/diff layer must not break or slow the current fast compare feature
- The current reports are useful for triage and anomaly detection, but they still have room to evolve toward more explicit grouped-difference reports.
- The two touched `tools/` scripts no longer emit the old `py_compile` escape warnings in this repo
- Current no-key compare semantics are still the old ones by design:
  - row order is ignored
  - duplicate-only differences are ignored
  - `row_count_a` and `row_count_b` still reflect raw row totals
- Local smoke tests should avoid port `5000` here, because another machine service is already bound there; `5081` worked for Flask route checks
- This machine also has no `curl` in PATH, so local HTTP smoke checks should prefer Python `urllib` or another available client

## Operator Notes For Next Conversation

- Read `PROJECT_STRUCTURE.md` first
- Read `ROUND_STATUS.md` second
- Read `RECOVERY_BACKLOG.md` for deferred work
- Keep changes minimal and behavior-preserving
- Use the project-local `.venv` only; do not rely on `/Users/menon/git/.venv`
- Natural next slices are:
  - continue reducing page-specific CSS duplication on top of the shared shell base now used by `index`, `track_record`, and `admin`
  - keep shrinking `static/app_search.js`, `static/app_bootstrap.js`, and `static/compare_dbs_render.js` by responsibility when there is measured gain
  - add focused frontend regression tests for the browser-validated invalid-state flows if the team wants them automated
  - harden the main SQLite contract in the Flask UI/backend layer without weakening DuckDB-first behavior
  - design richer diff/report outputs on top of the current compare results, preserving the fast path
  - review whether no-key compare should remain duplicate-insensitive or evolve to multiset semantics
  - deeper backend debt reduction in `interface/app_flask_local_search.py`
  - expand compare API payload-type validation if external callers send non-string fields today
