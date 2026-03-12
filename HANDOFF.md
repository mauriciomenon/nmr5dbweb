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
- The search page now also splits responsibilities into:
  - `static/app_results.js`
  - `static/app_priority.js`
- `static/compare_dbs.js` is now split into:
  - `static/compare_dbs.js`
  - `static/compare_dbs_render.js`
- The compare render layer now also uses:
  - `static/compare_dbs_diff_helpers.js`
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
- The main Flask UI/backend path now treats `SQLite` explicitly:
  - `/api/tables` can list SQLite tables directly
  - `/api/table` can read/filter/sort SQLite tables directly
  - `/api/search` now also serves SQLite search explicitly instead of blocking it in the main UI
- `.db` files now follow a predictable rule:
  - if the file header matches SQLite, the backend treats it as SQLite
  - otherwise the backend keeps the file on the DuckDB path
- The current reports are useful for triage and anomaly detection, but they still have room to evolve toward more explicit grouped-difference reports.
- Startup no longer persists `config.json` during import-time sanitization; runtime DB state now lives separately and is only persisted on explicit user actions.
- `/admin/status` now exposes:
  - `db_exists`
  - `startup_warnings`
  - backend capabilities for Access fallback, Access conversion, and DuckDB `_fulltext`
- Active DB resolution and engine eligibility in the Flask backend are now funneled through shared internal helpers instead of being repeated independently by each route.
- API paths that depend on the active DB now fail more consistently when the selected file no longer exists on disk.
- The repo now has a real JS validation baseline with `pnpm`, `eslint`, and `prettier`.
- `node_modules/` is now ignored in the product repo as part of that tooling baseline.
- `_fulltext` indexing is now rejected server-side for non-DuckDB engines instead of depending only on UI-side blocking.
- Browser success smoke now also exists in repo coverage for:
  - DuckDB `_fulltext` search success
  - DuckDB compare success
  - SQLite tracking success
- Browser regression coverage now also includes invalid inline feedback on the four main pages and the current no-active-DB admin indexing message.
- Browser regression coverage now also includes:
  - SQLite search success on the main page
  - compare pagination visibility
  - compare CSV export
- `static/compare_dbs_render.js` now derives extra operator hints from current compare results, without changing the fast compare engine or its API contract.
- `static/compare_dbs_render.js` now also highlights sensitive changed columns with example impacted keys for faster review.
- Safe cleanup Level A has now been applied with proof of use:
  - `notes/` was removed from the product repo path and copied to local ignored backup under `bkp_limpeza/notes/`
  - the old simplified backend `interface/app_flask_search.py` was removed from the product repo path and copied to `bkp_limpeza/interface/`
  - `interface/README.md` was rewritten to describe only the supported product backend path
- The admin file-management block in `interface/app_flask_local_search.py` is now less repetitive:
  - upload listing metadata uses a shared helper
  - upload target validation is centralized
  - Access conversion startup is isolated in a helper
  - delete cleanup of derived `.duckdb` files is centralized and covered by test
- The next three backend islands have now also been reduced with shared helpers:
  - admin settings (`/admin/set_auto_index`, `/admin/set_priority`)
  - record directory browsing (`/api/record_dirs`, `/api/browse_dirs`)
  - compare input validation (`/api/compare_db_tables`, `/api/compare_db_table_content`, `/api/compare_db_rows`)
- Shared compare-path validation now owns the repeated `db1_path`/`db2_path` existence checks, which reduces drift risk across the compare routes.
- Record-directory listing and browse enumeration are now isolated enough to be moved later without route rewrites.
- Search/table browsing now also uses shared context helpers:
  - browse endpoints only admit `duckdb` and `sqlite`
  - search endpoints admit `duckdb`, `sqlite`, and `access`
- Record tracking request parsing is now centralized, including validation of `filters`, `custom_path`, and `max_files`.
- Startup/config/runtime boundaries are now clearer:
  - loaded config is sanitized once
  - runtime active DB remains independent
  - admin status now exposes `persisted_db` separately from current runtime `db`
- Real operator Access samples in `output/` were used to confirm safe Access detection and correct rejection of unsupported browse operations.
- The next layer of backend reduction is now inside the implementation blocks, not only the route wrappers:
  - DuckDB and SQLite table browse now share clause/serialization helpers
  - DuckDB, SQLite, and Access search now share more result-ordering logic
  - record tracking now shares Access connection and engine-dispatch helpers
- Operator logging is slightly more coherent now:
  - `/client/log` and `/admin/logs` use capped shared entry handling
  - `/admin/logs` now reports `count` in addition to the log list
- Current file-review conclusion:
  - `converters/`, `tools/`, and `artifacts/` remain justified
  - `output/` is currently serving as a local validation area for real Access samples plus smoke fixtures
  - no extra move to `bkp_limpeza/` was justified in this slice
- ESLint config now has a single source of truth:
  - `eslint.config.mjs`
  - old `eslint.config.js` was retired
- The recent JS reliability findings were fixed in:
  - `static/app_search.js`
  - `static/app_results.js`
  - `static/app.js`
- The fast DuckDB search helper no longer reaches into global active DB state internally; it now uses the explicit `db_path` passed by the route.
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
  - keep shrinking `static/app_search.js`, `static/app_bootstrap.js`, and `static/compare_dbs_render.js` by responsibility where there is measured gain
  - decide whether the browser regression should bootstrap its own browser binary or remain environment-driven
  - keep hardening the main SQLite contract in the Flask UI/backend layer without weakening DuckDB-first behavior
  - design richer diff/report outputs on top of the current compare results, preserving the fast path
  - review whether no-key compare should remain duplicate-insensitive or evolve to multiset semantics
  - deeper backend debt reduction in `interface/app_flask_local_search.py`
  - continue reducing the remaining operator islands in `interface/app_flask_local_search.py` after upload, settings, browsing, and compare validation
  - continue reducing backend concentration in table/search implementation and record-tracking execution, not just request parsing
  - keep `output/` as a documented local validation area unless product requirements later demand a clearer sample-data convention
  - expand compare API payload-type validation if external callers send non-string fields today
