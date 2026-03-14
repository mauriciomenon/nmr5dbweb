# Round Status

## Current Slice: DeepScan Closure And Hard PR Continuation (2026-03-14)

### Goal

1. Close the active DeepScan blocker with minimal-risk patches.
2. Continue hard PR-comment fixes only where runtime/quality risk is real.
3. Keep browser behavior stable under focused regression checks.

### Applied

1. DeepScan closure in `static/compare_dbs_upload.js`:
   - validated parsed `saved` object before property use.
   - guarded required DOM refs (`nameSpan`, `pathInput`) before upload flow.
   - removed constant condition around `saved` after prior object guard.
   - normalized path value once (`currentPathValue`) and reused in later checks.
2. Hard-comment continuation in frontend:
   - `static/app_priority.js`: prevented duplicate DnD listener binding, preserved reversible remove flow, filtered invalid save payload values.
   - `static/app_results.js`: replaced `innerHTML` highlight rendering with DOM-safe fragment rendering; removed stale global export symbol.
   - `static/app_search.js`: backend delete errors now propagate to visible UI status.
   - `static/app_bootstrap.js`: bootstrap path now has top-level guarded error reporting.
   - `static/app_bootstrap_actions.js`: upload response handling hardened for non-JSON/HTTP failures; removed silent catch behavior.
   - `static/app_bootstrap_modals.js`: reduced duplicate overlay listeners and improved modal-status error detail.

### Commits In This Slice Sequence

- `23a1a90` fix(priority): avoid dnd rebinding and preserve reversible list edits
- `ef67cd4` fix(search): improve delete feedback and harden token highlight/export errors
- `fac94f5` fix(bootstrap): harden init path and upload response handling
- `d699502` fix(modals): reduce overlay listener duplication and improve status error detail
- `9f47772` fix(ui): harden safe highlight rendering and priority save flow
- `0d8c50d` fix(compare-upload): tighten null guards for saved state and path refs
- `35cd50c` fix(compare-upload): remove constant saved check and reuse normalized path

### Validation After Changes

- `pnpm -s eslint` on touched frontend files: passed.
- `PYTHONPATH=. uv run pytest -q tests/test_frontend_invalid_flows_browser.py`: passed (`18 passed`) in full runs.
- focused compare browser slice: passed (`2 passed`).
- repeated `kluster_code_review_auto` cycles: clean.

### Check Snapshot

1. `DeepScan`: `SUCCESS`.
2. `reviewDecision`: `APPROVED`.
3. `qlty check`: still pending/failing intermittently from broader legacy blocking set outside this short slice.

## Current Slice: PR Hard Comments Frontend Async/Modal Guard (2026-03-13)

### Goal

1. Resolve hard frontend review comments with real runtime risk first.
2. Keep patch minimal and behavior-preserving.
3. Confirm no regression in browser flow.

### Applied

1. `main.py`
   - preserve `UPLOAD_FOLDER` precedence as `CLI > env > default`.
2. `tests/test_main_port_fallback.py`
   - added regression test for env override preservation when `--upload-folder` is omitted.
3. `static/app.js`
   - added `.catch()` for async `/client/log` telemetry posts to avoid unhandled rejection noise.
   - added source-modal guard in delayed close timers to avoid closing a new modal opened after timer scheduling.
4. `static/app_bootstrap_actions.js`
   - auto-index toggle now uses guarded async request (`apiJSON` + `try/catch`) with consistent UI error feedback.
5. `static/app_bootstrap_modals.js`
   - `openSearchWorkspace` now awaits `refreshStatus()` before focus/select on `q`.
   - updated call sites to await the async flow.

### Commits In This Slice Sequence

- `9d03576` fix(startup): normalize upload folder env and assert no-fallback message
- `6d65a20` fix(startup): preserve UPLOAD_FOLDER env when flag is omitted
- `2b7a50b` fix(ui): harden modal timing and async log/index handlers

### Validation After Changes

- `uv run python -m py_compile main.py tests/test_main_port_fallback.py`: passed
- `uv run ruff check main.py tests/test_main_port_fallback.py`: passed
- `PYTHONPATH=. uv run pytest -q tests/test_main_port_fallback.py`: `7 passed`
- `pnpm -s eslint static/app.js static/app_bootstrap_actions.js static/app_bootstrap_modals.js`: passed
- `PYTHONPATH=. uv run pytest -q tests/test_frontend_invalid_flows_browser.py`: `18 passed`

### Real Pending Vs Noise (Now)

1. Real pending:
   - wait for fresh PR checks (`DeepScan`, `qlty`) and triage only new, still-valid findings.
2. Noise/legacy:
   - broad complexity/style debt in large legacy modules remains outside this short patch scope.

## Current Slice: Hard PR Comment Triage And Targeted Fixes (2026-03-13)

### Goal

1. Resolve high-impact bot findings first (data fidelity, stale state, export safety).
2. Keep patches minimal and behavior-preserving.
3. Keep control docs synchronized with the true repository state.

### Applied

1. Compare and render hardening:
   - `static/compare_dbs_render.js`
     - escaped summary fragments used in `innerHTML`
     - explicit side-value routing for `added`/`removed` row sections
   - `static/compare_dbs_upload.js`
     - robust non-JSON upload response handling
     - reset stale compare payload/meta when A/B path changes
     - restore table selection from saved `table` key
     - reset stale tables-overview cache/visibility on DB change
   - `static/compare_dbs_actions.js`
     - CSV formula injection neutralization for values starting with `=`, `+`, `-`, `@`
2. Conversion and startup reliability:
   - `access_convert.py`
     - strict mode no longer rejects valid all-empty user tables
     - strict mode still fails when there are real skipped tables
   - `main.py`
     - clearer split between `EADDRINUSE` and generic startup `OSError`
   - `tools/windows_access_smoke.py`
     - output guard and temporary cleanup in failure/no-table paths
3. Report conversion/cache path:
   - `tools/auto_compare_report.py`
     - explicit sqlite handle close
     - local timezone mtime output
     - safer derived-cache rebuild sequence to avoid wiping last good derivative on transient open failures

### Commits In This Slice Sequence

- `4112773` fix(compare): sanitize diff html, reset stale payload, and harden smoke output guard
- `6fc1fbc` fix(docs+compare): sync control docs and harden upload/smoke error paths
- `f16ca0f` fix(report): keep source mtime in local timezone
- `95d601a` fix(report): close sqlite handles explicitly in conversion paths
- `8fe3843` fix(core): harden rendering escapes, conversion strictness, and bind error handling
- `3aeb628` fix(review): address hard bot findings in compare state/render and report cache
- `8f230c8` fix(review): resolve hard findings on strict conversion, overview cache, and startup errors
- `4844060` fix(compare-csv): neutralize spreadsheet formula injection payloads

### Validation After Changes

- `pnpm -s eslint static/compare_dbs_render.js static/compare_dbs_upload.js static/compare_dbs_actions.js`: passed
- `uv run python -m py_compile access_convert.py tools/auto_compare_report.py main.py tests/test_main_port_fallback.py`: passed
- `uv run ruff check access_convert.py tools/auto_compare_report.py main.py tests/test_main_port_fallback.py`: passed
- `PYTHONPATH=. uv run pytest -q tests/test_main_port_fallback.py tests/test_access_convert_parser_strict.py tests/test_auto_compare_report.py`: passed
- `PYTHONPATH=. uv run pytest -q tests/test_compare_dbs.py tests/test_compare_db_rows_api.py`: passed
- browser compare smoke (`tests/test_frontend_invalid_flows_browser.py -k "compare_page or compare_pagination_and_export"`): passed
- windows smoke test remains environment-gated outside Windows: expected skip

### Real Pending Vs Legacy Noise (Now)

1. Real pending:
   - decide whether `tools/windows_access_smoke.py` should auto-delete temp output after success when `--output` is omitted
   - decide whether empty successful upload responses should be treated as hard error in compare upload flow
2. Legacy/noise still outside short patch scope:
   - `qlty` blocking set is mostly structural complexity/returns debt in large legacy modules
   - broad `bandit/qlty` heuristic flags around dynamic SQL construction where identifier validation already exists

## Current Slice: PR Triage And Reliability Guard Rails (2026-03-13)

### Goal

1. Sync control docs with the real repository and real open PR target.
2. Apply only low-risk reliability fixes in active compare/upload and Windows smoke paths.
3. Separate real PR findings from broad legacy noise.

### Applied

1. Confirmed PR context for this repo:
   - repo: `mauriciomenon/nmr5dbweb`
   - PR: `#2` (`codex/dev` -> `master`)
   - state: `OPEN`
2. Implemented low-risk reliability fixes:
   - `static/compare_dbs_upload.js`:
     - upload response now handles non-JSON body safely
     - clearer HTTP fallback error message
   - `tools/windows_access_smoke.py`:
     - temporary output cleanup on conversion failure or empty-table result
3. Updated control docs requested in this conversation:
   - `ROUND_STATUS.md`
   - `HANDOFF.md`
   - `PROJECT_STRUCTURE.md`
   - `RECOVERY_BACKLOG.md`
   - `interface/README.md`

### Validation After Changes

- `uv run python -m py_compile tools/windows_access_smoke.py`: passed
- `uv run ruff check tools/windows_access_smoke.py`: passed
- `pnpm -s eslint static/compare_dbs_upload.js`: passed
- `PYTHONPATH=. uv run pytest -q tests/test_access_conversion_windows_smoke.py`: `1 skipped` (expected outside Windows)

### Real Pending Vs Noise (Current)

1. Real pending (actionable, small):
   - keep handling unstable/non-JSON upload responses in compare flow (done in this slice)
   - keep Windows smoke temp artifacts bounded on failure paths (done in this slice)
2. Large legacy debt (not a short-slice blocker):
   - broad qlty complexity/returns warnings on large backend files
   - broad bandit/qlty heuristics on dynamic SQL areas already constrained by identifier validation
3. External checks status during this slice:
   - `DeepScan`: failing in current run
   - `qlty`: pending in current run
   - `cubic`: pending in current run

## Current Slice: Auto Compare Report Hardening And Operator Readability

### Goal

1. Keep the report path stable while improving readability for real operator review.
2. Make report metadata explicit and easier to audit across Access, DuckDB, and SQLite flows.
3. Add practical table controls in exported HTML without touching backend compare performance.
4. Keep behavior-preserving fixes focused on data fidelity (no synthetic formatting noise).

### Applied

1. Strengthened `tools/auto_compare_report.py` and its focused coverage in `tests/test_auto_compare_report.py`.
2. Added and refined interactive report outputs (`.html`, `.md`, `.txt`) with:
   - per-column quick filter
   - access-style quick mode (`contains` / `not_contains`)
   - column sort controls (`asc` / `desc`)
   - reset controls per table block
3. Improved metadata readability in report sources:
   - size rendered in MB
   - mtime rendered as `YYYY-MM-DD HH:MM`
   - clickable source/derived paths in HTML and Markdown outputs
   - explicit "engines used" section tied to where each engine participates
4. Reduced visual noise in report rendering:
   - removed heavy bold usage
   - normalized numeric display to avoid synthetic `.0` when value is integer
   - preserved decimals when they are real
   - compact long cells with clip + tooltip in HTML details
5. Hardened key/value fidelity in detail tables:
   - key header now uses real key columns (for example `UNIQID`)
   - integer display normalization includes `UNIQID`, `RTUNO`, and `PNTNO`
   - SOANLG forced columns no longer include `HLIM5`/`LLIM5` unless they are actually changed

### What Was Proved

- Report generation stayed stable while gaining practical review controls.
- Exported outputs became easier to read without changing compare backend semantics.
- The recent report-focused sequence remained covered by focused tests (`tests/test_auto_compare_report.py`) through iterative commits.

### Validation After Changes

- `uv run python -m py_compile tools/auto_compare_report.py tests/test_auto_compare_report.py`: passed
- `uv run ruff check tools/auto_compare_report.py tests/test_auto_compare_report.py`: passed
- `PYTHONPATH=. uv run pytest -q tests/test_auto_compare_report.py`: passed

## Current Slice: Full UI Playwright Reliability Sweep

### Goal

1. Raise real usability confidence on all main web pages (`/`, `/admin.html`, `/compare_dbs`, `/track_record`) with browser-level validation.
2. Cover missing UI operations that were not exercised by the prior smoke set.
3. Keep fixes minimal and focused on reliable operation, not broad refactor.

### Applied

1. Expanded browser suite in:
   - `tests/test_frontend_invalid_flows_browser.py`
2. Added new end-to-end coverage for:
   - shell options menu + help toggle + theme persistence
   - main files panel open/close, tab switch, delete flow
   - advanced search controls (`token_mode`, `tablesFilter`, `clearTablesFilter`)
   - search export-all CSV flow
   - admin upload -> active DB selection -> priority save -> index trigger
   - track page directory browse modal + selection + execution
   - compare options/help, overview toggle, and additional run mode checks
3. Hardened fixture realism:
   - sample data now pre-populates upload catalog with multiple DuckDB files to exercise real tab/file operations.

### What Was Proved

- Browser suite now validates both invalid flows and core success operations across all primary UI pages.
- Real user operations now covered include file lifecycle actions, advanced search inputs, compare summary/report controls, and track directory navigation.
- No backend/UI regressions detected in integrated API + browser validation.

### Validation After Changes

- `PYTHONPATH=. uv run --python 3.13 python -m py_compile tests/test_frontend_invalid_flows_browser.py`: passed
- `uv run --python 3.13 ruff check tests/test_frontend_invalid_flows_browser.py`: passed
- `PYTHONPATH=. uv run --python 3.13 pytest -q tests/test_frontend_invalid_flows_browser.py`: `17 passed`
- `PYTHONPATH=. uv run --python 3.13 pytest -q tests/test_app_flask_local_search_api.py tests/test_compare_db_rows_api.py tests/test_compare_dbs.py tests/test_find_record_across_dbs_access_fallback.py tests/test_main_port_fallback.py tests/test_frontend_invalid_flows_browser.py`: `132 passed`

### Remaining Superficial Pending

1. Add drag-and-drop priority reorder browser assertion in `admin.html` (today we validate save/update, not DnD movement).
2. Add browser assertion for compare CSV content under each isolated change type (`changed` only, `added` only, `removed` only).
3. Add browser assertion for track modal `dirUpBtn` navigation behavior on nested directories.

## Current Slice: Help Matrix, JS Lint Recovery, And Windows Access Smoke Path

### Goal

1. Clarify in-product help for Access/SQLite/DuckDB usage and compare/index behavior.
2. Remove the reported JS quality regressions in `static/app.js` and `static/app_results.js`.
3. Add a real Windows-oriented smoke path for `.accdb -> .duckdb` conversion.
4. Improve browser regression coverage for compare CSV export content.

### Applied

1. Updated in-page help:
   - `static/index.html`
   - `static/compare_dbs.html`
2. Fixed JS warnings:
   - no-inner-declarations block in `static/app.js`
   - constant conditions in `static/app_results.js`
3. Reduced duplication in DB selection flow:
   - added shared `requestSelectDb(...)` helper in `static/app.js`
4. Added Windows smoke tooling for Access conversion:
   - `tools/windows_access_smoke.py`
   - `tests/test_access_conversion_windows_smoke.py` (Windows + env gated)
5. Expanded browser smoke for compare CSV export:
   - `tests/test_frontend_invalid_flows_browser.py`

### Validation After Changes

- `pnpm -s eslint static`: passed
- `uv run python -m py_compile tools/windows_access_smoke.py tests/test_access_conversion_windows_smoke.py`: passed
- `uv run ruff check tools/windows_access_smoke.py tests/test_access_conversion_windows_smoke.py`: passed
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --with pytest --with playwright --with duckdb --with flask --with rapidfuzz --with werkzeug python -m pytest -q tests/test_frontend_invalid_flows_browser.py -k "compare_pagination_and_export" tests/test_access_conversion_windows_smoke.py`: passed

## Current Slice: Validation Pipeline With Real Local Files

### Goal

1. Build a reproducible local pipeline that materializes canonical `duckdb` and `sqlite` files from real samples.
2. Measure key runtime timings (browse/search/compare) and store evidence in repo-local reports.
3. Improve compare report reliability/readability without touching the fast keyed compare backend path.
4. Prove browser behavior with Playwright on the compare flow.

### Applied

1. Added `tools/prepare_validation_artifacts.py`:
   - scans `output/` recursively
   - writes canonical inputs into `artifacts/validation/input/`
   - materializes canonical `duckdb` and `sqlite` outputs under:
     - `artifacts/validation/derived/duckdb/`
     - `artifacts/validation/derived/sqlite/`
   - emits `artifacts/validation/reports/dataset_manifest.json`
2. Added `tools/benchmark_validation_flows.py`:
   - times list/read/search flows on generated artifacts
   - times keyed compare between compatible DuckDB pairs
   - emits:
     - `artifacts/validation/reports/benchmark_times.csv`
     - `artifacts/validation/reports/benchmark_summary.md`
3. Added operator-facing docs for this validation pipeline:
   - `artifacts/validation/reports/README.md`
4. Hardened compare summary rendering in `static/compare_dbs_render.js`:
   - stable anchor for view-mode controls (`#compareViewModeAnchor`)
   - no fragile `nth-child` selector coupling
   - broader HTML escaping in report sections fed by DB values
5. Expanded compare smoke assertions in browser tests:
   - `tests/test_frontend_invalid_flows_browser.py`
   - validates A/B labels, volume/saldo text, and view-mode controls.

### What Was Proved

- The local validation pipeline now runs end-to-end and stores reproducible artifacts and timing reports.
- Access `.accdb` conversion is still environment-gated on this machine (`pyodbc`/driver not available).
- Smoke fixtures under `output/smoke/` are now converted both ways and benchmarked.
- Compare summary controls no longer depend on brittle DOM position.
- Playwright compare smoke passed with the new assertions.

### Validation After Changes

- `uv run python -m py_compile tools/prepare_validation_artifacts.py tools/benchmark_validation_flows.py`: passed
- `uv run ruff check tools/prepare_validation_artifacts.py tools/benchmark_validation_flows.py interface`: passed
- `pnpm -s eslint static/compare_dbs_render.js`: passed
- `env PYTHONPATH=. uv run --with duckdb --with pandas python tools/prepare_validation_artifacts.py`: passed
- `env PYTHONPATH=. uv run --with duckdb --with flask --with rapidfuzz python tools/benchmark_validation_flows.py`: passed
- `env PYTHONPATH=. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --with pytest --with playwright --with duckdb --with flask --with rapidfuzz --with werkzeug python -m pytest -q tests/test_frontend_invalid_flows_browser.py -k "compare_page or compare_pagination_and_export"`: `2 passed`
- `env PYTHONPATH=. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --with pytest --with duckdb --with flask --with rapidfuzz python -m pytest -q tests/test_compare_dbs.py tests/test_compare_db_rows_api.py`: `27 passed`

## Current Slice: Operator-Focused Search And Anomaly Reading

### Goal

1. Make the main search screen useful for wide real operator tables
2. Push compare reading closer to anomaly review
3. Keep reducing duplication in browse/search without broad refactor

### Applied

1. `static/app_results.js` now renders search results as an operator-focused workbench:
   - sticky score and leading columns
   - long-field handling
   - compact preview cards per row
   - same renderer reused for full table open
2. `static/compare_dbs_render.js` now adds:
   - families most affected
   - observed state transitions
   on top of the existing compare summary
3. `interface/app_flask_local_search.py` now shares more browse/search internals:
   - table-page query execution
   - Access search column selection
   - Access row text/payload building

### What Was Proved

- Search output is more readable for real wide tables without changing the API.
- Compare output now surfaces more operational anomaly signals before row-by-row inspection.
- Access search path repeats less backend logic while keeping the current behavior.

### Validation After Changes

- `pnpm exec prettier --check "static/**/*.js" "*.{js,json}"`: passed
- `pnpm exec eslint static`: passed
- `node --check static/app_results.js`: passed
- `node --check static/compare_dbs_render.js`: passed
- `./.venv/bin/python -m py_compile $(rg --files -g "*.py")`: passed
- `ruff`, `ty`: passed
- focused `pytest`: `62 passed`

## Current Slice: Search Usability With Better Table Reading

### Goal

1. Make the main search result table useful with real operator data
2. Improve diff reading toward anomaly review, not just row dumps
3. Reduce backend duplication in browse/search without broad refactor

### Applied

1. Rebuilt `static/app_results.js` around a more usable data-table renderer.
2. Search results now surface:
   - fields brought to the front
   - long-text fields called out
   - sticky score/key columns
   - safer truncation for long values
3. Full table view (`Abrir`) now uses the same renderer instead of a second raw table path.
4. `static/compare_dbs_render.js` now also highlights:
   - change patterns grouped by affected columns
5. `interface/app_flask_local_search.py` now shares:
   - table-page query execution
   - search scoring logic
   - score-by-table calculation
   across DuckDB, SQLite, and Access paths more consistently.

### What Was Proved

- The main search screen is now much more readable for wide real-world tables.
- The compare screen now gives a better first-pass review of repeated anomalies.
- Backend browse/search logic repeats less without changing the fast compare path.

### Validation After Changes

- `pnpm exec eslint static`: passed
- `pnpm exec prettier --check "static/**/*.js" "*.{js,json}"`: passed
- `node --check static/app_results.js`: passed
- `node --check static/compare_dbs_render.js`: passed
- `./.venv/bin/python -m py_compile $(rg --files -g "*.py")`: passed
- `ruff`, `ty`: passed
- focused `pytest`: `62 passed`

## Current Slice: ESLint Legacy Compatibility And Better Diff Reading

### Goal

1. Make the repo lintable both locally and in older analyzers still pinned to `ESLint 8.15.0`
2. Improve diff readability for operator review without touching the fast compare engine

### Applied

1. Added legacy ESLint fallback files:
   - `.eslintrc.cjs`
   - `.eslintignore`
2. Kept `eslint.config.mjs` as the local flat-config baseline.
3. Improved compare diff reading in:
   - `static/compare_dbs_render.js`
   - `static/compare_dbs.html`
4. New report blocks now show:
   - keys to review first
   - columns most impacted

### What Was Proved

- Local lint still works with the flat config baseline.
- Legacy `eslint@8.15.0` can now lint the repo successfully.
- The compare UI now surfaces a more actionable first-pass reading of the diff without changing the compare SQL path.

### Validation After Changes

- `pnpm exec eslint static`: passed
- `pnpm dlx eslint@8.15.0 static --ext .js`: passed
- `pnpm exec prettier --check "static/**/*.js" "*.{js,json}"`: passed
- `node --check static/compare_dbs_render.js`: passed
- `./.venv/bin/python -m py_compile $(rg --files -g "*.py")`: passed
- `ruff`, `ty`: passed
- focused `pytest`: `62 passed`

## Current Slice: JS Tooling, SQLite Search, And Stable Operator Flows

### Goal

1. Add a real JS validation baseline to the product repo
2. Remove the remaining immediate-use block for SQLite search on the main screen
3. Reduce backend route repetition without broad refactor
4. Expand browser validation into a more reliable operator suite
5. Improve diff reading without touching the fast compare engine

### Applied

1. Added JS tooling in the product repo:
   - `package.json`
   - `eslint.config.js`
   - `.prettierrc.json`
   - `.prettierignore`
2. Installed and validated:
   - `eslint`
   - `prettier`
   - `@eslint/js`
   - `globals`
3. Tuned the ESLint baseline to the repo's current browser-script model:
   - no fake failures for cross-file globals
   - no forced `var` cleanup in this stabilization slice
4. Hardened `interface/app_flask_local_search.py` with smaller shared helpers for:
   - current DB resolution mapped to route responses
   - integer query parsing
   - search and table request parsing
5. Enabled SQLite search on the main search screen through a real backend path:
   - `fallback_search_sqlite(...)`
   - `/api/search` now serves DuckDB, SQLite, and Access with explicit engine handling
6. Returned `db_engine` in `/api/tables` and `/api/table` responses for clearer frontend behavior.
7. Updated the frontend to stop blocking SQLite search in the main UI.
8. Expanded browser coverage for:
   - invalid inline feedback
   - DuckDB search success
   - SQLite search success
   - DuckDB compare success
   - compare pagination visibility plus CSV export
   - SQLite tracking success
9. Improved compare summary rendering with an extra "Colunas sensiveis para revisar" block based on current diff output only.
10. Added `node_modules/` to `.gitignore` as part of the JS tooling baseline.

### What Was Proved

- The product repo now has enforceable JS formatting and lint checks via `pnpm`.
- SQLite can now be searched from the main UI instead of being blocked after selection.
- The Flask backend now repeats less current-DB validation logic across its main operator routes.
- The compare report UI is more useful for fast anomaly review without changing the fast compare backend path.
- The browser suite now exercises a broader set of real success paths.

### Validation After Changes

- `pnpm exec eslint static`: passed
- `pnpm exec prettier --check "static/**/*.js" "*.{js,json}"`: passed
- `./.venv/bin/python -m py_compile $(rg --files -g "*.py")`: passed
- `./.venv/bin/ruff check interface/app_flask_local_search.py tests/test_app_flask_local_search_api.py tests/test_frontend_invalid_flows_browser.py`: passed
- `./.venv/bin/ty check interface/app_flask_local_search.py tests/test_app_flask_local_search_api.py tests/test_frontend_invalid_flows_browser.py`: passed
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/python -m pytest -q tests/test_app_flask_local_search_api.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py tests/test_frontend_invalid_flows_browser.py`: `45 passed`

## Current Slice: Safe Cleanup Level A

### Goal

1. Remove clearly unrelated or legacy files from the product path only after proving they are not in the supported runtime flow
2. Keep a local backup in an ignored folder before any cleanup
3. Adapt the main product docs to the real supported backend path

### Applied

1. Created local backup area:
   - `bkp_limpeza/`
   - ignored via `.gitignore`
2. Backed up and then removed from the product repo path:
   - `notes/*.md`
   - `interface/app_flask_search.py`
3. Backed up `interface/README.md` before rewriting it for the product path.
4. Updated docs to describe only the supported backend/product flow:
   - `interface/app_flask_local_search.py`
   - current search/compare/track behavior
5. Left `converters/`, `tools/`, and `artifacts/` in place because they still have current references and product/analysis value.

### What Was Proved

- `notes/*.md` had no role in the runtime product path.
- `interface/app_flask_search.py` was only referenced by docs and not by the current product startup path.
- `converters/`, `tools/`, and `artifacts/` still have active references in the repo and were correctly kept for now.

### Validation After Changes

- proof-of-use scan completed before cleanup
- backup copies stored locally under `bkp_limpeza/`
- product docs updated to the supported backend path only

## Current Slice: Admin Upload Flow Consolidation

### Goal

1. Reduce the concentration of the upload/select/delete/list block in the main Flask backend
2. Keep the same route contracts while moving repeated file-handling logic into smaller helpers
3. Preserve immediate usability and prove the behavior with focused tests

### Applied

1. Added internal helpers in `interface/app_flask_local_search.py` for:
   - upload listing metadata
   - upload-path resolution and validation inside `UPLOAD_DIR`
   - immediate-select decision for uploaded DB files
   - Access conversion output naming
   - Access conversion startup
   - derived-file cleanup on delete
2. Rewired these routes to the helpers without changing their external contract:
   - `/admin/list_uploads`
   - `/admin/upload`
   - `/admin/select`
   - `/admin/delete`
3. Added focused regression coverage for:
   - upload listing metadata
   - delete removing the derived converted DuckDB file

### What Was Proved

- The admin file-management block now has less duplicated path/filename logic.
- Access-conversion startup is more isolated from the route body.
- Delete now keeps the source/derived cleanup behavior covered by test.

### Validation After Changes

- `./.venv/bin/python -m py_compile $(rg --files -g "*.py")`: passed
- `./.venv/bin/ruff check interface/app_flask_local_search.py tests/test_app_flask_local_search_api.py`: passed
- `./.venv/bin/ty check interface/app_flask_local_search.py tests/test_app_flask_local_search_api.py`: passed
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/python -m pytest -q tests/test_app_flask_local_search_api.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py tests/test_frontend_invalid_flows_browser.py`: `47 passed`

## Current Slice: Immediate-Use Hardening And Stable Browser Smoke

### Goal

1. Remove the remaining immediate-use ambiguity around the active DB state in the Flask backend
2. Turn the browser smoke into a broader stable suite for success and invalid flows
3. Evolve diff reporting at the presentation layer without touching the fast compare engine

### Applied

1. Consolidated active-DB and engine checks in `interface/app_flask_local_search.py` with:
   - `get_current_db_context(...)`
   - `build_admin_status()`
2. Reused that backend context in:
   - `/admin/status`
   - `/admin/start_index`
   - `/api/tables`
   - `/api/table`
   - `/api/search`
3. Added explicit missing-file behavior for the active DB path, instead of letting each route fail differently.
4. Added a report-oriented summary block in `static/compare_dbs_render.js` based on existing compare results only.
5. Expanded the browser regression suite to cover:
   - invalid inline feedback on all main pages
   - successful DuckDB search flow
   - successful DuckDB compare flow
   - successful SQLite tracking flow
6. Updated the browser invalid-flow test to match the current admin message for no active DB before indexing.

### What Was Proved

- The backend now resolves active DB state and engine eligibility through one narrower internal path instead of repeating the same checks across routes.
- Missing active DB files are now rejected consistently in API paths that depend on them.
- The browser suite now covers both invalid and successful operator flows across the four main pages.
- The compare report UI gained more useful operational hints without altering the current fast compare path.

### Validation After Changes

- `./.venv/bin/python -m py_compile $(rg --files -g "*.py")`: passed
- `./.venv/bin/ruff check interface/app_flask_local_search.py tests/test_app_flask_local_search_api.py tests/test_frontend_invalid_flows_browser.py`: passed
- `./.venv/bin/ty check interface/app_flask_local_search.py tests/test_app_flask_local_search_api.py tests/test_frontend_invalid_flows_browser.py`: passed
- `timeout 60s node --check static/compare_dbs_render.js`: passed
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/python -m pytest -q tests/test_app_flask_local_search_api.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py tests/test_frontend_invalid_flows_browser.py`: `43 passed`

## Round

Slice 1: repo zero-state and control files

## Branch / Source

- Local work dir: `/Users/menon/git/nmr5dbweb`
- Current local branch: `master`
- Source branch at clone time: `minha-alteracao`
- Product default branch: `master`

## Objective For This Round

1. Save structural discovery inside the repo
2. Remove machine-specific/runtime state from version control
3. Keep the patch minimal and low risk

## Verified Facts

- The original local repo `/Users/menon/git/mdb2sql` was not the student fork branch.
- The student fork branch `minha-alteracao` was cloned successfully into `/Users/menon/git/nmr5dbweb`.
- `gh` is authenticated as `mauriciomenon`.
- `mauriciomenon/nmr5dbweb` was created and published.
- `origin` now points to the product repo.
- `upstream` now points to `allysonalmeidaa/mdb2sql_fork`.

## Baseline Validation Before Changes

- `uv run python -m py_compile ...`: passed
- `ruff check .`: failed with many issues
- `pytest -q`: local shebang problem
- `uv run pytest -q`: failed collection because `duckdb` is missing in the uv runtime

## Current Findings Snapshot

- Runtime state was versioned in `interface/config.json`
- `duckdb.exe` was versioned in the repo root
- Local inspection file existed under `tools/`
- Temporary dependency snapshot existed under `notes/`
- `static/app.js` has duplicated function blocks

## Applied In This Slice

1. Added control files:
   - `PROJECT_STRUCTURE.md`
   - `RECOVERY_BACKLOG.md`
   - `ROUND_STATUS.md`
   - `HANDOFF.md`
2. Stopped versioning runtime config:
   - removed `interface/config.json`
   - added `interface/config.example.json`
   - ignored `interface/config.json` in git
3. Removed machine-specific tracked leftovers:
   - `duckdb.exe`
   - `tools/inspect_aux_unidad.py`
   - `notes/versions_tmp.txt`

## Validation After Changes

- `uv run python -m py_compile ...`: passed
- `ruff check .`: still failing with pre-existing repo debt outside this slice
- `uv run pytest -q tests/test_compare_dbs.py tests/test_compare_db_rows_api.py`: blocked by missing `duckdb` in the uv runtime

## Follow-up Slice: Clean Setup And Test Environment

### Goal

Make the project boot and validate from a clean `uv`-managed Python environment.

### Applied

1. Added `requirements-dev.txt` with:
   - `-r requirements.txt`
   - `pytest`
   - `ruff`
   - `ty`
   - explicit `pluggy`, `iniconfig`, `pygments`
2. Updated `README.md` to document:
   - `uv venv --python 3.12.8 .venv`
   - `uv pip sync requirements.txt`
   - `uv pip sync requirements-dev.txt`
   - main validation commands

### What Was Proved

- A clean `uv` venv with Python 3.12.8 can be created successfully.
- `uv pip sync requirements-dev.txt` installs the runtime and validation stack.
- Focused tests now pass in a clean environment.

### Validation In Clean Venv

- `python -m py_compile $(rg --files -g "*.py")`: passed
- `pytest -q tests/test_compare_dbs.py tests/test_compare_db_rows_api.py`: 8 passed
- `ruff check .`: still failing with existing repo-wide debt
- `ty check .`: still failing with existing repo-wide debt

### Findings From This Slice

- The repo still has no `pyproject.toml` or `uv.lock`.
- `uv run ...` alone is not enough here because the repo is requirements-based, not project-metadata-based.
- `pytest` needed explicit `pluggy`, `iniconfig`, and `pygments` to become stable in the clean synced environment used in this repo.

## Next Expected Step

After this slice:

1. start the next stabilization slice on top of `master`
2. fix the next highest-value issues without broad refactor
3. keep backlog and handoff files updated each round

## Follow-up Slice: Remove Critical JS Duplication

### Goal

Remove confirmed duplicate hot-path functions from `static/app.js` with the smallest possible patch and no layout changes.

### Applied

1. Removed the older duplicated definitions of:
   - `refreshTables`
   - `selectUpload`
   - `renderResults`
   - `openTable`
   - `exportTableCsv`
   - `exportResultsCsv`
2. Kept the newer definitions already present later in the file as the single source of behavior.
3. Preserved the current `DOMContentLoaded` setup and existing UI structure.

### What Was Proved

- The six critical duplicated functions now appear exactly once in `static/app.js`.
- The edited JS file still parses cleanly.
- The patch is deletion-only for the duplicated blocks and does not alter visual layout.

### Validation After Changes

- `node --check static/app.js`: passed
- `uv run python -m py_compile $(rg --files -g "*.py")`: passed
- `uv run ruff check .`: still failing with pre-existing repo-wide debt
- `uv run ty check .`: still failing with pre-existing repo-wide debt and environment/import resolution issues
- `uv run pytest -q tests/test_compare_dbs.py tests/test_compare_db_rows_api.py`: failed in this machine state because `uv run` picked an ambient pytest/plugin combination outside the repo setup
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run python -m pytest -q tests/test_compare_dbs.py tests/test_compare_db_rows_api.py`: failed because the ambient `/Users/menon/git/.venv` does not currently have `pytest`

### Findings From This Slice

- The most obvious frontend duplication risk in `static/app.js` was reduced without refactor.
- Validation on this machine still depends on cleaning up the ambient `uv` runtime selection, even though the previously documented clean synced venv baseline remains valid.

## Follow-up Slice: Local Project Venv And Generic Search Repair

### Goal

Stop mixing the repo with the parent-directory virtualenv, pin the project to its own `uv` venv, and fix the missing generic search function in `tools/encontrar_registro_em_bds.py`.

### Applied

1. Recreated the project-local `.venv` with `uv` and Python `3.13.12`.
2. Stopped using `uv run` for validation in this repo and switched to direct calls through `./.venv/bin/...`.
3. Implemented `buscar_generico_em_tabela(...)` in `tools/encontrar_registro_em_bds.py`.
4. Added focused regression coverage in `tests/test_find_record_generic.py` for:
   - candidate-column search
   - `--try-all-cols` fallback behavior
5. Tightened a few low-risk typing paths in the same tool:
   - safe Access connection raises
   - safe DuckDB count fetch handling
   - explicit `require_duckdb()` gate for optional module access

### What Was Proved

- The repo now has a working project-local venv at `/Users/menon/git/nmr5dbweb/.venv`.
- The local interpreter is `Python 3.13.12`.
- The generic search mode no longer references an undefined function.
- The new focused tests pass and prove the repaired behavior in DuckDB.

### Validation After Changes

- `./.venv/bin/python -V`: `Python 3.13.12`
- `./.venv/bin/python -m py_compile $(rg --files -g "*.py")`: passed
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/python -m pytest -q tests/test_find_record_generic.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py`: `10 passed`
- `./.venv/bin/ty check tools/encontrar_registro_em_bds.py tests/test_find_record_generic.py`: passed
- `./.venv/bin/ruff check tools/encontrar_registro_em_bds.py tests/test_find_record_generic.py`: still fails because the legacy tool file has broad pre-existing style debt unrelated to the repaired bug

### Findings From This Slice

- The environment drift problem was real: `uv run` was resolving against `/Users/menon/git/.venv` and even a global `pytest`.
- For this repo, validation should currently prefer the project-local `.venv` directly until a stronger `uv` project configuration exists.
- `tools/encontrar_registro_em_bds.py` still carries heavy style debt, but the concrete functional hole in generic search is now closed and covered by test.

## Follow-up Slice: Backend API Hardening

### Goal

Harden the Flask backend around upload, index startup, and search parameter handling without broad refactor.

### Applied

1. Switched internal imports in `interface/app_flask_local_search.py` to package-qualified `interface.*` imports.
2. Typed optional backend dependencies and guarded their use more explicitly:
   - `pyodbc`
   - `convert_access_to_duckdb`
   - `create_or_resume_fulltext`
3. Hardened `/admin/upload`:
   - reject filenames that sanitize to empty
   - reject unsupported extensions before saving
   - avoid saving Access uploads when the converter is unavailable
   - treat `.db`, `.sqlite`, and `.sqlite3` like immediate-select local databases
4. Hardened `/admin/select` and `/admin/delete` filename sanitization.
5. Hardened `/admin/start_index`:
   - reject invalid `chunk` and `batch`
   - reject missing current DB
   - removed the fallback import dance inside the worker thread
6. Hardened `/api/search` and `api_search_duckdb(...)`:
   - safer integer parsing for `per_table`, `candidate_limit`, and `total_limit`
   - safer connection closing on DuckDB search path
7. Reduced a localized lint-debt block in `fallback_search_access(...)`.
8. Added focused API regression tests in `tests/test_app_flask_local_search_api.py`.

### What Was Proved

- Focused backend API validation is now green:
  - upload edge cases
  - index startup error paths
  - search parameter validation
  - compare and generic-search regressions

## Follow-up Slice: Frontend Module Split And Real Browser Validation

### Goal

Reduce frontend maintenance risk by splitting the two largest page scripts and then validate the real rendered pages in a browser session.

### Applied

1. Split the main search/frontend script into:
   - `static/app.js` as the shared core/state module
   - `static/app_search.js` for search/result actions
   - `static/app_bootstrap.js` for DOM startup and bindings
2. Split the compare page script into:
   - `static/compare_dbs.js` for flow/state/request handling
   - `static/compare_dbs_render.js` for diff rendering and pagination UI helpers
3. Updated page asset loading:
   - `static/index.html` now loads the three search modules in dependency order
   - `static/compare_dbs.html` now loads the compare flow and render modules separately
4. During browser validation, fixed one concrete admin-page regression in `static/admin.html`:
   - the page no longer requests `/api/tables` when no active DB exists
   - the priority area now shows a controlled warning state instead of a `400` console error
5. Ran real browser validation through Playwright against:
   - `/`
   - `/compare_dbs`
   - `/track_record`
   - `/admin.html`

### What Was Proved

- The large frontend files are now split into smaller operational modules without changing Flask routes or DOM ids.
- The search page still exposes the expected global functions through the new module layout.
- The compare page still exposes the expected global handlers after the split.
- The admin page no longer emits the previous `/api/tables` error when no DB is selected.
- Real browser navigation and rendering now complete successfully on all four main pages.

### Validation After Changes

- `./.venv/bin/python -m py_compile $(rg --files -g "*.py")`: passed
- `node --check static/app.js static/app_search.js static/app_bootstrap.js static/ui_utils.js static/shell.js static/compare_dbs.js static/compare_dbs_render.js`: passed
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/python -m pytest -q tests/test_compare_dbs.py tests/test_compare_db_rows_api.py tests/test_app_flask_local_search_api.py`: `30 passed`
- `./.venv/bin/ruff check interface/app_flask_local_search.py interface/compare_dbs.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py tests/test_app_flask_local_search_api.py`: passed
- `./.venv/bin/ty check interface/app_flask_local_search.py interface/compare_dbs.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py tests/test_app_flask_local_search_api.py`: passed
- Playwright browser validation:
  - index page loaded, with only a non-blocking missing `favicon.ico`
  - compare page loaded with zero console errors
  - track page loaded with zero console errors
  - admin page loaded cleanly after the no-DB guard fix
- Focused backend API validation is now green in the project-local venv.
- The upload and search paths now fail earlier and more explicitly on bad input.
- Optional backend dependencies are now guarded without silent fallback.

## Follow-up Slice: Frontend Flow Hardening And Browser UX Pass

### Goal

Harden the user-facing web flows so search, admin, compare, and tracking expose clear inline state for empty, loading, success, and error conditions without broad backend changes.

### Applied

1. Hardened the search flow in `static/app_search.js`:
   - added inline search-meta status updates for empty query, no DB, blocked search, error, empty result, and success
   - removed several alert-driven branches where the page already had visible status areas
   - improved priority modal status text and save feedback
   - reduced noisy success/error handling for DB select/delete actions
2. Hardened the page bootstrap in `static/app_bootstrap.js`:
   - unified search-modal opening into one path
   - disabled upload and index buttons during in-flight actions
   - normalized Enter-to-search behavior in the modal
3. Hardened the admin flow in `static/admin.html`:
   - stored the latest uploads/status payloads locally
   - blocked index start when no DB is active
   - blocked index start when the indexer is unavailable or already running
   - added button-busy handling and better inline feedback for upload, priority save, and index start
4. Hardened compare in `static/compare_dbs.js` and `static/compare_dbs_render.js`:
   - added button-busy handling for load tables, export, and overview generation
   - improved compare status messages for missing input, paging, export, and failures
   - added a clearer no-difference result state for the current filter/page
5. Hardened tracking in `static/track_record.html`:
   - moved missing-input validation to inline status/flow hints
   - added button-busy handling during execution
   - added Ctrl/Cmd+Enter as a fast trigger for running the analysis
6. Ran browser validation on real page interactions:
   - opened search modal without DB
   - triggered admin index action without DB
   - triggered compare table mapping without A/B paths
   - triggered track analysis without required filters

### What Was Proved

- The web UI now handles the most common invalid states inline instead of relying on alert popups.
- The admin page no longer makes an avoidable failing index request when no DB is active.
- Compare and track now surface validation failures directly in the page flow, which is easier to audit and less disruptive.
- The browser pass confirms the flows above without console errors in the validated scenarios.

### Validation After Changes

- `./.venv/bin/python -m py_compile $(timeout 60s rg --files -g "*.py")`: passed
- `node --check static/app.js static/app_search.js static/app_bootstrap.js static/ui_utils.js static/shell.js static/compare_dbs.js static/compare_dbs_render.js`: passed
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/python -m pytest -q tests/test_compare_dbs.py tests/test_compare_db_rows_api.py tests/test_app_flask_local_search_api.py`: `30 passed`
- `./.venv/bin/ruff check interface/app_flask_local_search.py interface/compare_dbs.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py tests/test_app_flask_local_search_api.py`: passed
- `./.venv/bin/ty check interface/app_flask_local_search.py interface/compare_dbs.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py tests/test_app_flask_local_search_api.py`: passed
- Playwright browser validation:
  - search modal opens with disabled search and no console error when no DB is active
  - admin index action is blocked locally with a visible warning when no DB is active
  - compare "Mapear tabelas comuns" now reports the missing A/B paths inline
  - track "Rastrear registro" now reports missing filters inline

### Validation After Changes

- `./.venv/bin/python -m py_compile $(rg --files -g "*.py")`: passed
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/python -m pytest -q tests/test_app_flask_local_search_api.py tests/test_find_record_generic.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py`: `16 passed`
- `./.venv/bin/ty check interface/app_flask_local_search.py tests/test_app_flask_local_search_api.py tests/test_find_record_generic.py tests/test_compare_db_rows_api.py`: passed
- `./.venv/bin/ruff check interface/app_flask_local_search.py tests/test_app_flask_local_search_api.py tests/test_find_record_generic.py tests/test_compare_db_rows_api.py`: passed

### Findings From This Slice

- The repo still has broader maintainability debt in `interface/app_flask_local_search.py`, but the highest-risk error paths around upload, search, and index startup are now covered.
- The project-local `.venv` with Python `3.13.12` is the reliable validation target for this repo.

## Follow-up Slice: SQL-Based Table Content Compare

### Goal

Remove the full-table Python materialization in `compare_table_content_duckdb(...)` and move the no-key table comparison into DuckDB SQL, without changing the current API contract.

### Applied

1. Reworked `interface/compare_dbs.py::compare_table_content_duckdb(...)` to:
   - keep schema discovery via read-only connections
   - attach both DuckDB files into an in-memory connection
   - compute the diff summary with SQL instead of Python `set(...)`
2. Preserved current external semantics:
   - row order is ignored
   - duplicate-only differences are still ignored
   - `row_count_a` and `row_count_b` still report raw table row counts
3. Added focused regression tests in `tests/test_compare_dbs.py` for:
   - same content in different order
   - real row differences
   - duplicate-only differences
   - no common columns
4. Tightened result extraction in the same module to satisfy `ty` without broad refactor.

### What Was Proved

- The no-key compare path no longer pulls the full table contents into Python memory just to count differences.
- The API-facing behavior remains compatible with the previous implementation for order and duplicate handling.
- The compare module now has direct regression coverage for the no-key path that was previously untested.

### Validation After Changes

- `./.venv/bin/python -m py_compile $(timeout 60s rg --files -g "*.py")`: passed with pre-existing `SyntaxWarning` output from unrelated tool docstrings
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/python -m pytest -q tests/test_compare_dbs.py tests/test_compare_db_rows_api.py`: `12 passed`
- `./.venv/bin/ty check interface/compare_dbs.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py`: passed
- `./.venv/bin/ruff check interface/compare_dbs.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py`: passed

### Findings From This Slice

- The old no-key compare path was both memory-heavier than necessary and semantically easy to misread because it used Python `set(...)` over full query results.
- There are still broader compare concerns outside this slice:
  - `compare_table_duckdb(...)` still interpolates identifiers directly into SQL
  - the product still exposes two distinct compare models: keyed row diff and no-key content diff

## Follow-up Slice: Compare Identifier Hardening And Strict API Filters

### Goal

Harden the compare stack around SQL identifiers, client-side filter validation, and local tool-script warnings without changing the current compare contract.

### Applied

1. Hardened `interface/compare_dbs.py`:
   - added safe quoting for SQL literals and identifiers
   - switched schema discovery to `information_schema.columns`
   - applied quoted table/column references in `compare_table_content_duckdb(...)`
   - applied quoted table/column references in `compare_table_duckdb(...)`
   - attached both databases in read-only mode for keyed compare as well
   - added explicit validation for:
     - missing table in `db1` or `db2`
     - missing `key_columns`
     - missing `compare_columns`
2. Hardened `/api/compare_db_rows` in `interface/app_flask_local_search.py`:
   - reject invalid `key_columns`
   - reject invalid `compare_columns`
   - reject invalid `change_types` instead of silently dropping values
   - reject malformed `key_filter`
   - reject `key_filter` columns outside `key_columns`
   - reject `changed_column` not present in resolved `compare_columns`
   - return `400` on compare-layer `ValueError` instead of leaking as `500`
3. Expanded regression coverage:
   - quoted table and column identifiers
   - missing key column rejection
   - invalid `key_filter`
   - invalid `change_types`
   - invalid `changed_column`
4. Cleaned the localized `ruff` debt and `py_compile` warnings in:
   - `tools/build_consolidated_interactive_report_pt.py`
   - `tools/analyze_single_table_by_column.py`

### What Was Proved

- The compare layer now handles quoted and space-containing identifiers safely.
- Invalid compare filters now fail explicitly at the API boundary instead of being ignored or downgraded into ambiguous behavior.
- The project-local validation baseline is clean again for this slice, including `py_compile` on the touched tool scripts.

### Validation After Changes

- `./.venv/bin/python -m py_compile $(timeout 60s rg --files -g "*.py")`: passed
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/python -m pytest -q tests/test_compare_dbs.py tests/test_compare_db_rows_api.py`: `18 passed`
- `./.venv/bin/ty check interface/compare_dbs.py interface/app_flask_local_search.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py`: passed
- `./.venv/bin/ruff check interface/compare_dbs.py interface/app_flask_local_search.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py tools/build_consolidated_interactive_report_pt.py tools/analyze_single_table_by_column.py`: passed

### Findings From This Slice

- The compare backend is now less permissive on malformed payloads; callers that relied on silent coercion will now receive `400`.
- The next unresolved compare decision is semantic, not structural: whether compare-without-key should keep ignoring duplicate-only differences or move to true multiset comparison.

## Follow-up Slice: Compare Pagination Correctness

### Goal

Stop `/api/compare_db_rows` from truncating the compare result before backend filters and pagination are applied.

### Applied

1. Updated `interface/app_flask_local_search.py` so this route no longer passes `row_limit` into `compare_table_duckdb(...)`.
2. Kept `row_limit` and `page_size` strictly as output pagination controls for the route.
3. Added focused API regression coverage in `tests/test_compare_db_rows_api.py` for:
   - `key_filter` with `row_limit=1`
   - `change_types` with `row_limit=1`
   - `changed_column` with `row_limit=1`
   - page 2 with `row_limit=1`
4. Used `monkeypatch` in the new tests to prove the route now calls the compare layer with `limit=None` and paginates only after filtering.

### What Was Proved

- Backend filters no longer operate on a prematurely truncated diff set.
- Pagination across page 2 and later no longer collapses back to page 1 because of an upstream SQL limit.
- The route now matches the frontend contract, where `row_limit` is effectively the requested page size.

### Validation After Changes

- `./.venv/bin/python -m py_compile $(timeout 60s rg --files -g "*.py")`: passed
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/python -m pytest -q tests/test_compare_db_rows_api.py tests/test_compare_dbs.py`: `22 passed`
- `./.venv/bin/ty check interface/app_flask_local_search.py tests/test_compare_db_rows_api.py`: passed
- `./.venv/bin/ruff check interface/app_flask_local_search.py tests/test_compare_db_rows_api.py`: passed

### Findings From This Slice

- The compare route is now correct for filtering and pagination, but it still paginates in Python after loading the full diff set returned by `compare_table_duckdb(...)`.
- If very large compare outputs become a real performance bottleneck, the next measured optimization should move filter/pagination deeper into the SQL layer instead of reintroducing truncation before filtering.

## Follow-up Slice: Dedicated SQL Compare Paging Engine

### Goal

Replace the route-level Python filtering and pagination path with a dedicated SQL-backed compare paging engine.

### Applied

1. Added `compare_table_duckdb_paged(...)` in `interface/compare_dbs.py`.
2. Kept `compare_table_duckdb(...)` intact for existing direct callers and regression coverage.
3. Moved into SQL for the keyed compare route:
   - `key_filter`
   - `change_types`
   - `changed_column`
   - `page`
   - `page_size`
4. Preserved the current API contract:
   - global `summary` remains unfiltered
   - `rows` are paged
   - `total_filtered_rows` and `total_pages` reflect the filtered result set
5. Added stable paging order by key columns plus `change_type`.
6. Switched `/api/compare_db_rows` in `interface/app_flask_local_search.py` to the new paged engine and removed the old Python-side filtering/pagination block.
7. Expanded regression coverage:
   - direct unit coverage for `compare_table_duckdb_paged(...)`
   - route coverage with the paged engine monkeypatched

### What Was Proved

- The compare route no longer needs to materialize the full diff set in Python just to filter and paginate.
- SQL-backed pagination preserves the existing JSON contract expected by `static/compare_dbs.html`.
- The old compare engine still works for existing direct tests while the route now uses the paged path.

### Validation After Changes

- `./.venv/bin/python -m py_compile $(timeout 60s rg --files -g "*.py")`: passed
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/python -m pytest -q tests/test_compare_dbs.py tests/test_compare_db_rows_api.py`: `24 passed`
- `./.venv/bin/ty check interface/compare_dbs.py interface/app_flask_local_search.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py`: passed
- `./.venv/bin/ruff check interface/compare_dbs.py interface/app_flask_local_search.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py`: passed

### Findings From This Slice

- The route-level performance bottleneck from Python-side compare pagination is now closed.
- The compare module now carries two keyed compare engines with overlapping setup logic, which is acceptable for the stabilization phase but is the next cleanup candidate if we keep extending this area.

## Follow-up Slice: Consolidated Keyed Compare Internals

### Goal

Remove duplicated keyed-compare setup logic in `interface/compare_dbs.py` without changing the public compare contract.

### Applied

1. Added shared internal helpers in `interface/compare_dbs.py` for:
   - path validation
   - common-column resolution
   - keyed compare column validation
   - SQL plan assembly
   - compare-row hydration into the existing JSON shape
2. Introduced `_KeyedComparePlan` to keep the shared compare metadata explicit and local to the module.
3. Refactored both public keyed compare entry points to use the same internal plan and row-mapping path:
   - `compare_table_duckdb(...)`
   - `compare_table_duckdb_paged(...)`
4. Preserved the current route and test contract without touching layout or unrelated backend flows.

### What Was Proved

- The two keyed compare paths now share one internal source of truth for validation, SQL setup, and row shaping.
- The refactor did not change the external behavior already covered by the compare unit/API tests.
- The compare area is less likely to drift the next time keyed compare behavior is extended.

### Validation After Changes

- `./.venv/bin/python -m py_compile $(timeout 60s rg --files -g "*.py")`: passed
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/python -m pytest -q tests/test_compare_dbs.py tests/test_compare_db_rows_api.py`: `24 passed`
- `./.venv/bin/ty check interface/compare_dbs.py interface/app_flask_local_search.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py`: passed
- `./.venv/bin/ruff check interface/compare_dbs.py interface/app_flask_local_search.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py`: passed

### Findings From This Slice

- The internal duplication between the two keyed compare engines is now closed.
- The next compare decision is semantic rather than structural: whether compare-without-key should keep its duplicate-insensitive behavior.

## Follow-up Slice: Frontend Information Architecture Refresh

### Goal

Reorganize the Flask/static web pages to make the operational flow clearer without changing the backend contract.

### Applied

1. Reworked the shell, hero, and task grouping of the four web pages:
   - `static/index.html`
   - `static/admin.html`
   - `static/compare_dbs.html`
   - `static/track_record.html`
2. Preserved the existing DOM ids used by the JavaScript and backend routes so the frontend behavior stays wired to the current Flask endpoints.
3. Promoted task-oriented navigation across pages:
   - search
   - compare
   - track record
   - admin
4. Reframed the search page around:
   - workspace status
   - next-step actions
   - file/table explorer
5. Rebuilt the admin page into a real operations screen for:
   - upload
   - DB selection
   - priority ordering
   - index startup
6. Reorganized compare and track pages so the setup flow is visually separated from the result-reading area.
7. Improved labels and action names to reduce ambiguity in the operator flow.

### What Was Proved

- The page reorganization did not require backend endpoint changes.
- The existing compare/search API tests still pass after the layout rewrite.
- The Flask app still serves the expected HTML routes for:
  - `/`
  - `/admin.html`
  - `/compare_dbs`
  - `/track_record`

### Validation After Changes

- `./.venv/bin/python -m py_compile $(timeout 60s rg --files -g "*.py")`: passed
- `./.venv/bin/ruff check interface/app_flask_local_search.py interface/compare_dbs.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py tests/test_app_flask_local_search_api.py`: passed
- `./.venv/bin/ty check interface/app_flask_local_search.py interface/compare_dbs.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py tests/test_app_flask_local_search_api.py`: passed
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/python -m pytest -q tests/test_compare_dbs.py tests/test_compare_db_rows_api.py tests/test_app_flask_local_search_api.py`: `30 passed`
- `node --check static/app.js && node --check static/ui_utils.js`: passed
- Flask route smoke check on alternate port `5081`: passed for `/`, `/admin.html`, `/compare_dbs`, `/track_record`

### Findings From This Slice

- The frontend now has better task separation, but visual shell/theme rules are still duplicated across multiple static HTML files.
- Browser-level validation with Playwright is currently blocked on this machine because the Chromium binary is not installed.
- Port `5000` is occupied by another local service on this machine, so local UI smoke checks should prefer an alternate port such as `5081`.

## Follow-up Slice: Shared Frontend Shell Extraction

### Goal

Reduce the duplicated shell/theme code across the static web pages without changing Flask routes, frontend ids, or backend behavior.

### Applied

1. Added shared frontend assets:
   - `static/shell.css`
   - `static/shell.js`
2. Updated the four web pages to use the shared shell assets:
   - `static/index.html`
   - `static/admin.html`
   - `static/compare_dbs.html`
   - `static/track_record.html`
3. Removed the repeated theme/options JavaScript blocks from:
   - `static/index.html`
   - `static/compare_dbs.html`
   - `static/track_record.html`
   - `static/admin.html`
4. Moved shared theme/menu behavior into `static/shell.js`.
5. Moved the shared layout shell rules used by the search/compare/track pages into `static/shell.css`.
6. Kept all existing ids and page-specific scripts intact so the current JS wiring remains stable.

### What Was Proved

- The shared shell assets are served correctly by Flask as `/shell.css` and `/shell.js`.
- The extracted shell did not break the compare/search/backend-focused validation baseline.
- The four pages still render through the expected routes while now depending on one shared shell entrypoint.

### Validation After Changes

- `./.venv/bin/python -m py_compile $(timeout 60s rg --files -g "*.py")`: passed
- `./.venv/bin/ruff check interface/app_flask_local_search.py interface/compare_dbs.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py tests/test_app_flask_local_search_api.py`: passed
- `./.venv/bin/ty check interface/app_flask_local_search.py interface/compare_dbs.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py tests/test_app_flask_local_search_api.py`: passed
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/python -m pytest -q tests/test_compare_dbs.py tests/test_compare_db_rows_api.py tests/test_app_flask_local_search_api.py`: `30 passed`
- `node --check static/app.js && node --check static/ui_utils.js && node --check static/shell.js`: passed
- Flask route smoke check on alternate port `5081`: passed for `/`, `/admin.html`, `/compare_dbs`, `/track_record`
- Shared asset smoke check on alternate port `5081`: passed for `/shell.css` and `/shell.js`

### Findings From This Slice

- The shared theme/options behavior is now centralized, which lowers the cost of future UI changes.
- CSS duplication still exists in page-specific styles, but the shell-level drift risk is lower than before.

## Follow-up Slice: Shared Workbench Components And Compare Flow Cleanup

### Goal

Push the web UI beyond shell extraction by sharing more component-level rules across the static pages and by simplifying the compare page flow where the operator actually works.

### Applied

1. Expanded `static/shell.css` so it now also carries shared component rules for:
   - tabs and options menu
   - primary/ghost buttons used by the search and compare shells
   - shared flow hints
   - compare/track card, form, workflow, and action primitives
2. Removed the duplicated tab/options/button/form/workflow CSS blocks from:
   - `static/index.html`
   - `static/compare_dbs.html`
   - `static/track_record.html`
3. Reorganized step 2 of `static/compare_dbs.html` into clearer operator panels:
   - table + key definition
   - compare scope
   - visual filters
   - page/limit controls
4. Reframed step 3 of `static/compare_dbs.html` so the result area now has:
   - a clearer result note
   - a more explicit tables overview action
   - cleaner separation between summary and detailed diff reading
5. Consolidated compare page request logic around shared helpers for:
   - `POST` JSON calls
   - compare busy-state handling
   - compare metadata refresh
   - payload collection from the current form
6. Reused the same compare request path for:
   - direct compare
   - page changes
   - export pagination
   - tables overview generation
   - restored compare state

### What Was Proved

- The search/compare/track pages now depend on a broader shared shell/component layer without changing backend ids or Flask routes.
- The compare page still preserves the current API contract while using less duplicated request logic.
- The Flask routes for the touched UI still serve correctly on an alternate local port after the compare layout cleanup.

### Validation After Changes

- `./.venv/bin/python -m py_compile $(timeout 60s rg --files -g "*.py")`: passed
- `node --check static/app.js && node --check static/ui_utils.js && node --check static/shell.js`: passed
- extracted inline script check for `static/compare_dbs.html` with `node --check`: passed
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/python -m pytest -q tests/test_compare_dbs.py tests/test_compare_db_rows_api.py tests/test_app_flask_local_search_api.py`: `30 passed`
- `./.venv/bin/ruff check interface/app_flask_local_search.py interface/compare_dbs.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py tests/test_app_flask_local_search_api.py`: passed
- `./.venv/bin/ty check interface/app_flask_local_search.py interface/compare_dbs.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py tests/test_app_flask_local_search_api.py`: passed
- Flask route smoke check on alternate port `5081`: passed for `/`, `/admin.html`, `/compare_dbs`, `/track_record`, `/shell.css`, `/shell.js`

### Findings From This Slice

- Component-level CSS drift is lower now for search/compare/track, but `static/admin.html` still carries a more isolated visual system than the other pages.
- `static/compare_dbs.html` is more maintainable than before, but it still has a large inline script and remains a future extraction candidate.
- This machine still lacks `curl` in PATH, so local HTTP smoke checks should prefer Python `urllib` or another available client.

## Follow-up Slice: Admin Shell Alignment And Compare Script Extraction

### Goal

Pull the admin page into the same shared component system and move the large compare-page script out of the HTML file without changing ids, routes, or payload behavior.

### Applied

1. Expanded `static/shell.css` so it now also carries the shared admin component layer for:
   - action buttons
   - shell cards and section headers
   - form controls
   - stats, steps, status panels, and upload entries
   - responsive admin workbench layout rules
2. Removed the duplicated admin shell/component CSS from `static/admin.html` while preserving the page-specific theme and DOM structure.
3. Extracted the large inline compare script from `static/compare_dbs.html` into the new dedicated asset `static/compare_dbs.js`.
4. Rewired `static/compare_dbs.html` to load:
   - `/shell.js`
   - `/compare_dbs.js`
5. Kept the current compare/search/admin ids, Flask routes, and API payload contract unchanged.

### What Was Proved

- `static/admin.html` now uses the same shared component foundation as the other product pages.
- `static/compare_dbs.html` is materially smaller and easier to maintain because its page logic now lives in `static/compare_dbs.js`.
- The extracted compare asset is served correctly by Flask and did not break the backend-focused validation baseline.

### Validation After Changes

- `./.venv/bin/python -m py_compile $(timeout 60s rg --files -g "*.py")`: passed
- `./.venv/bin/ruff check interface/app_flask_local_search.py interface/compare_dbs.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py tests/test_app_flask_local_search_api.py`: passed
- `./.venv/bin/ty check interface/app_flask_local_search.py interface/compare_dbs.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py tests/test_app_flask_local_search_api.py`: passed
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/python -m pytest -q tests/test_compare_dbs.py tests/test_compare_db_rows_api.py tests/test_app_flask_local_search_api.py`: `30 passed`
- `node --check static/app.js && node --check static/ui_utils.js && node --check static/shell.js && node --check static/compare_dbs.js`: passed
- Flask route smoke check on alternate port `5081`: passed for `/`, `/admin.html`, `/compare_dbs`, `/track_record`
- Shared asset smoke check on alternate port `5081`: passed for `/shell.css`, `/shell.js`, `/compare_dbs.js`

### Findings From This Slice

- The four HTML pages now share a broader common visual/component layer, which lowers the cost of future UX cleanup.
- `static/compare_dbs.js` is still a large page module and should eventually be split by responsibility after the operator flow settles.
- Local UI smoke remains CLI/browser-light on this machine because Playwright still has no Chromium binary installed.

## Follow-up Slice: Search Bootstrap Dedup And Shared Shell Base

### Goal

Remove the remaining duplicated search/admin bootstrap path in `static/app.js` and move the common search/track shell base out of page-local CSS without changing ids, Flask routes, or data flow.

### Applied

1. Removed the older duplicated frontend block from `static/app.js`, including the second copies of:
   - modal/bootstrap wiring
   - priority modal setup
   - search execution
   - search utility/render helpers
2. Kept a single active bootstrap path in `static/app.js` and reattached the unique behaviors that still mattered there:
   - upload button flow
   - `dbSearchBtn`
   - priority modal refresh/save bindings
3. Expanded `static/shell.css` with the shared search/track shell base for:
   - body background
   - sticky header shell
   - brand mark/title/subtitle
   - common container padding
   - responsive header/container padding
4. Removed the duplicated search/track shell base CSS from:
   - `static/index.html`
   - `static/track_record.html`
5. Kept the existing DOM ids, Flask endpoints, and frontend payload behavior intact.

### What Was Proved

- `static/app.js` now has one active bootstrap path and one active definition for the previously duplicated search/priority helpers.
- The search and track pages now depend on a broader shared shell base instead of duplicating body/header shell rules inline.
- The local Flask smoke still serves the touched pages and assets correctly after the JS/CSS consolidation.

### Validation After Changes

- `./.venv/bin/python -m py_compile $(timeout 60s rg --files -g "*.py")`: passed
- `./.venv/bin/ruff check interface/app_flask_local_search.py interface/compare_dbs.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py tests/test_app_flask_local_search_api.py`: passed
- `./.venv/bin/ty check interface/app_flask_local_search.py interface/compare_dbs.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py tests/test_app_flask_local_search_api.py`: passed
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/python -m pytest -q tests/test_compare_dbs.py tests/test_compare_db_rows_api.py tests/test_app_flask_local_search_api.py`: `30 passed`
- `node --check static/app.js && node --check static/ui_utils.js && node --check static/shell.js && node --check static/compare_dbs.js`: passed
- Flask route smoke check on alternate port `5081`: passed for `/`, `/track_record`, `/compare_dbs`, `/admin.html`
- Shared asset smoke check on alternate port `5081`: passed for `/shell.css`, `/shell.js`, `/compare_dbs.js`, `/app.js`

### Findings From This Slice

- The remaining frontend risk is now more about file size and responsibility boundaries than raw duplicate logic.
- `static/app.js` is still large, but the duplicated search/priority/bootstrap path is now closed.
- Search and track still keep page-specific visual rules, but the shell-level base is now centralized.

## Follow-up Slice: Frontend Invalid-Flow Regression And SQLite Contract Hardening

### Goal

Automate the main invalid frontend flows, keep shrinking the JS modules that still carry mixed responsibilities, and harden the main Flask path so `DuckDB` and `SQLite` are treated explicitly instead of by loose extension guesses.

### Applied

1. Split search page responsibilities further:
   - added `static/app_results.js` for result rendering/export/open-table behavior
   - added `static/app_priority.js` for priority modal behavior
   - rewired `static/index.html` to load the new files before `static/app_search.js`
2. Split compare render helpers out of the render file:
   - added `static/compare_dbs_diff_helpers.js`
   - reduced `static/compare_dbs_render.js` to summary/section/render responsibilities
   - rewired `static/compare_dbs.html` to load the helper asset explicitly
3. Hardened the Flask backend in `interface/app_flask_local_search.py`:
   - added explicit engine detection with support for:
     - `DuckDB`
     - `SQLite`
     - `Access`
   - treat `.db` as `SQLite` only when the file header matches SQLite, otherwise keep the path on the `DuckDB` route
   - added explicit SQLite table listing and table-read helpers
   - kept the fast DuckDB compare path unchanged
   - rejected search-on-main-screen for SQLite with a clear API error instead of letting it fail implicitly in DuckDB code
4. Added focused API regression coverage for:
   - SQLite table listing
   - SQLite table read with filter/sort
   - `.db` engine detection for both SQLite and DuckDB
   - clear rejection of main-screen search when the active DB is SQLite
5. Added browser regression coverage for the four invalid flows already validated manually:
   - search without active DB
   - admin index start without DB
   - compare without A/B paths
   - tracking without required filters
6. Updated the main search UI status logic to expose SQLite as a distinct state instead of silently treating it like DuckDB.

### What Was Proved

- `static/app_search.js` is materially smaller and now focuses on file-selection and search request flow, not on result rendering and priority modal behavior.
- `static/compare_dbs_render.js` is materially smaller and now focuses on diff rendering, while the helper logic lives in its own file.
- The main Flask UI/backend path now distinguishes SQLite from DuckDB in `/api/tables`, `/api/table`, and `/api/search`.
- The keyed compare fast path in DuckDB was preserved while SQLite support became more explicit and predictable for table browsing.
- The invalid UI flows now have repeatable browser regression coverage in the repo.

### Validation After Changes

- `./.venv/bin/python -m py_compile $(timeout 60s rg --files -g "*.py")`: passed
- `./.venv/bin/ruff check interface/app_flask_local_search.py tests/test_app_flask_local_search_api.py tests/test_frontend_invalid_flows_browser.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py`: passed
- `./.venv/bin/ty check interface/app_flask_local_search.py tests/test_app_flask_local_search_api.py tests/test_frontend_invalid_flows_browser.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py`: passed
- `timeout 60s node --check static/app.js ... static/compare_dbs_render.js`: passed for all touched JS assets
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/python -m pytest -q tests/test_app_flask_local_search_api.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py`: `35 passed`
- Real browser validation passed via Playwright MCP on:
  - `/`
  - `/admin.html`
  - `/compare_dbs`
  - `/track_record`
  with the expected inline invalid-state feedback on each route

### Findings From This Slice

- The product now has a clearer `DuckDB` vs `SQLite` contract in the main UI/backend path, but the search feature remains intentionally DuckDB-first.
- The browser regression file exists and covers the right invalid flows, but local pytest execution still depends on a Playwright browser binary being present on the machine.
- The next heavy backend target remains `interface/app_flask_local_search.py`, but its format/engine edge handling is now less ambiguous than before.

## Follow-up Slice: Immediate-Use Hardening, Success Smoke, And Runtime Startup Cleanup

### Goal

Remove the highest-risk immediate-use issues in the Flask runtime/startup path, expand browser coverage from invalid-only to success smoke, and keep splitting the frontend operator files without changing the fast compare contract.

### Applied

1. Hardened runtime/startup behavior in `interface/app_flask_local_search.py`:
   - stopped persisting `config.json` during module import/startup
   - introduced explicit runtime DB state separate from startup sanitization
   - exposed `startup_warnings`, `db_exists`, and backend capabilities in `/admin/status`
   - moved indexing/conversion failure reporting from `print(...)` to Flask logging
   - rejected `_fulltext` indexing for non-DuckDB engines at the API level
2. Continued frontend responsibility split on the main search page:
   - added `static/app_bootstrap_modals.js`
   - added `static/app_bootstrap_actions.js`
   - reduced `static/app_bootstrap.js` to orchestration only
   - rewired `static/index.html` to load the new files explicitly
3. Continued frontend responsibility split on compare:
   - added `static/compare_dbs_upload.js`
   - added `static/compare_dbs_actions.js`
   - reduced `static/compare_dbs.js` to shared compare state and helper functions
   - rewired `static/compare_dbs.html` to load the new files explicitly
4. Expanded browser regression coverage:
   - kept the invalid-flow browser test
   - added a success smoke covering:
     - main search with `_fulltext`
     - compare between two DuckDB files
     - tracking over a SQLite file
5. Added focused backend regression coverage for the new startup/runtime behavior:
   - `/admin/start_index` now rejects SQLite explicitly
   - `/admin/status` exposes capabilities and startup warnings
6. Ran a real Playwright MCP smoke on the local Flask server with generated test data in `output/smoke/`.

### What Was Proved

- The app no longer rewrites runtime config on import just to sanitize startup state.
- The active DB remains available through explicit runtime state while still being persisted only on real user actions.
- Browser success flows now exist for the three main operator paths:
  - search
  - compare
  - track
- `static/app_bootstrap.js` and `static/compare_dbs.js` are both smaller and cleaner entry points than before this slice.
- The fast keyed compare flow remains intact; no contract or behavior change was made there.

### Validation After Changes

- `./.venv/bin/python -m py_compile $(timeout 60s rg --files -g '*.py')`: passed
- `timeout 60s node --check static/app.js static/app_search.js static/app_priority.js static/app_results.js static/app_bootstrap_modals.js static/app_bootstrap_actions.js static/app_bootstrap.js static/compare_dbs.js static/compare_dbs_upload.js static/compare_dbs_actions.js static/compare_dbs_diff_helpers.js static/compare_dbs_render.js static/ui_utils.js static/shell.js`: passed
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/python -m pytest -q tests/test_app_flask_local_search_api.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py tests/test_frontend_invalid_flows_browser.py`: `37 passed, 2 skipped`
- `./.venv/bin/ruff check interface/app_flask_local_search.py tests/test_app_flask_local_search_api.py tests/test_frontend_invalid_flows_browser.py`: passed
- `./.venv/bin/ty check interface/app_flask_local_search.py tests/test_app_flask_local_search_api.py tests/test_frontend_invalid_flows_browser.py`: passed
- Real browser smoke via Playwright MCP on `127.0.0.1:5081`:
  - `/` with successful DuckDB upload and search
  - `/compare_dbs` with successful keyed compare
  - `/track_record` with successful SQLite tracking
  - `/admin.html` with active DB visible and no browser console errors

### Findings From This Slice

- The most immediate runtime risk was not in compare speed anymore; it was startup/config/runtime-state coupling in the Flask layer.
- Browser regression is now materially more useful because it covers a success path instead of only validation failures.
- The next backend target should stay inside `interface/app_flask_local_search.py`, but now around reducing concentration of responsibilities, not around startup safety.

## Current Slice: Admin Settings And Record Browsing Consolidation

### Scope Completed

1. Reduced the `status/admin settings` block in `interface/app_flask_local_search.py`.
2. Reduced the `record dir browsing` block in `interface/app_flask_local_search.py`.
3. Hardened shared validation across the three compare endpoints without touching `interface/compare_dbs.py`.

### What Changed

- Added shared helpers for:
  - priority normalization
  - boolean admin setting parsing
  - configured record directory listing
  - browse-root and child-directory enumeration
  - common compare input validation for `db1_path` and `db2_path`
- Rewired these routes to shared helpers:
  - `/admin/set_auto_index`
  - `/admin/set_priority`
  - `/api/record_dirs`
  - `/api/browse_dirs`
  - `/api/compare_db_tables`
  - `/api/compare_db_table_content`
  - `/api/compare_db_rows`
- Added focused API coverage for:
  - `set_auto_index`
  - `set_priority`
  - `record_dirs`
  - `browse_dirs`
  - compare endpoints with missing files

### What Was Proved

- The backend now has less route-local duplication in the operator/admin and compare-validation paths.
- Directory browsing behavior is now isolated enough to change safely later without touching the routes again.
- Missing-file compare failures are now produced from one backend validation path instead of three ad hoc implementations.

### Validation After Changes

- `./.venv/bin/python -m py_compile $(timeout 60s rg --files -g '*.py')`: passed
- `./.venv/bin/ruff check interface/app_flask_local_search.py tests/test_app_flask_local_search_api.py`: passed
- `./.venv/bin/ty check interface/app_flask_local_search.py tests/test_app_flask_local_search_api.py`: passed
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/python -m pytest -q tests/test_app_flask_local_search_api.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py tests/test_frontend_invalid_flows_browser.py`: `55 passed`

## Current Slice: Search Table Browsing And Runtime Boundary Consolidation

### Scope Completed

1. Reduced `search/table browsing` concentration in `interface/app_flask_local_search.py`.
2. Hardened the `record tracking flow` request parsing in `interface/app_flask_local_search.py`.
3. Tightened the boundary between persisted config and runtime DB state.
4. Performed a conservative file-organization review with real Access samples from `output/`.

### What Changed

- Added shared config/runtime helpers for:
  - config defaults
  - config sanitization at startup
  - persisted DB path introspection
- Added shared flow helpers for:
  - browseable DB context resolution
  - searchable DB context resolution
  - record-tracking request parsing
- Rewired these routes to shared helpers:
  - `/api/tables`
  - `/api/table`
  - `/api/search`
  - `/api/find_record_across_dbs`
- `admin/status` now exposes `persisted_db` separately from the active runtime `db`.
- Added focused API coverage for:
  - Access DB rejection on browse endpoints
  - invalid `max_files` on record tracking
  - persisted-vs-runtime DB status visibility

### Real Data Proof

- Used the real file `output/2025-11-05 DB4.accdb` for a local proof of use.
- Confirmed:
  - `detect_db_engine(...)` returns `access`
  - `/api/tables` rejects it cleanly for browse with `Engine nao suportada para esta operacao: access`
- This proves the product is not silently misrouting real operator Access files through the DuckDB/SQLite browse path.

### File Organization Review

- Reviewed tracked garbage candidates such as `.DS_Store`, `__pycache__/`, and `.pyc`.
- No tracked leftovers of that class were found in the repo index during this slice.
- No cleanup move was needed in this pass.

### Validation After Changes

- `./.venv/bin/python -m py_compile $(timeout 60s rg --files -g '*.py')`: passed
- `./.venv/bin/ruff check interface/app_flask_local_search.py tests/test_app_flask_local_search_api.py`: passed
- `./.venv/bin/ty check interface/app_flask_local_search.py tests/test_app_flask_local_search_api.py`: passed
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/python -m pytest -q tests/test_app_flask_local_search_api.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py tests/test_frontend_invalid_flows_browser.py`: `57 passed`

## Current Slice: Table Search Implementation And Tracking Dispatch Consolidation

### Scope Completed

1. Reduced the `table/search implementation` concentration inside `interface/app_flask_local_search.py`.
2. Reduced repeated engine-dispatch and Access connection code in `interface/find_record_across_dbs.py`.
3. Improved operator-facing log/status consistency.
4. Performed a conservative repo-file review using real Access samples from `output/`.

### What Changed

- Added shared helpers in `interface/app_flask_local_search.py` for:
  - capped log handling
  - server/client log entry construction
  - result ordering by `priority_tables`
  - search response payload construction
  - row serialization for table browse
  - table filter/order clause construction
  - column discovery for DuckDB and SQLite
- Reused those helpers in:
  - `/client/log`
  - `/admin/logs`
  - `/api/table`
  - DuckDB search path
  - SQLite search path
  - Access fallback search path
- Reduced repeated code in `interface/find_record_across_dbs.py` by introducing:
  - `connect_access(...)`
  - `list_tables_for_engine(...)`
  - `list_columns_for_engine(...)`
  - `build_engine_where_parts(...)`
- Added focused API coverage for:
  - `client/log` plus `admin/logs`
  - DuckDB table browsing
  - DuckDB search ordering by priority table
  - successful record tracking through SQLite

### Real Data Proof

- Reused the real Access sample `output/2025-11-05 DB4.accdb` during local proof.
- Confirmed again that:
  - the file is detected as `access`
  - browse endpoints reject it safely instead of misrouting it as DuckDB/SQLite

### File Review

- `converters/`, `tools/`, and `artifacts/` still have active repo references and remain justified.
- `output/` is now clearly acting as a local validation/smoke area with real operator samples plus generated smoke fixtures.
- No additional move to `bkp_limpeza/` was justified in this slice.

### Validation After Changes

- `./.venv/bin/python -m py_compile $(timeout 60s rg --files -g '*.py')`: passed
- `./.venv/bin/ruff check interface/app_flask_local_search.py interface/find_record_across_dbs.py tests/test_app_flask_local_search_api.py`: passed
- `./.venv/bin/ty check interface/app_flask_local_search.py interface/find_record_across_dbs.py tests/test_app_flask_local_search_api.py`: passed
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/python -m pytest -q tests/test_app_flask_local_search_api.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py tests/test_frontend_invalid_flows_browser.py`: `61 passed`
- `pnpm exec eslint static`: passed
- `pnpm exec prettier --check "static/**/*.js" "*.{js,json}"`: passed

## Current Slice: ESLint Migration And JS Reliability Fixes

### Scope Completed

1. Published the user-generated ESLint config migration first, as its own slice.
2. Fixed the concrete JS reliability findings raised on `app_search.js`, `app_results.js`, and `app.js`.
3. Simplified one more bad coupling in the DuckDB fast search path without changing behavior.
4. Formalized the current role of `output/` in project control docs.

### What Changed

- Replaced the old CommonJS ESLint config with a single flat-config file:
  - `eslint.config.mjs`
- Removed the duplicate config source:
  - `eslint.config.js`
- Kept the lint scope pragmatic for current repo needs:
  - browser scripts under `static/`
  - ignore local/generated paths such as `output/`, `node_modules/`, `.venv/`, and `bkp_limpeza/`
- Fixed the JS issues reported by static analysis:
  - null-check cleanup in `static/app_search.js`
  - redundant `row_json` conditions in `static/app_results.js`
  - constant-condition cleanup in `static/app.js`
  - cleaner conversion/indexer status handling in `static/app.js`
- Simplified the fast DuckDB search path in `interface/app_flask_local_search.py`:
  - `api_search_duckdb(...)` now uses the `db_path` explicitly passed from the route instead of reaching back into global active-state lookup
- Added focused regression coverage proving that the fast DuckDB search helper uses the explicit path it receives.

### Decision On `output/`

- `output/` is now treated as a formal local validation area:
  - real operator sample DBs
  - smoke fixtures
- It is useful and currently justified.
- It is not part of the supported product runtime contract.
- No move/rename was executed in this slice; only the project decision was documented.

### Validation After Changes

- `./.venv/bin/python -m py_compile $(timeout 60s rg --files -g '*.py')`: passed
- `./.venv/bin/ruff check interface/app_flask_local_search.py interface/find_record_across_dbs.py tests/test_app_flask_local_search_api.py`: passed
- `./.venv/bin/ty check interface/app_flask_local_search.py interface/find_record_across_dbs.py tests/test_app_flask_local_search_api.py`: passed
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ./.venv/bin/python -m pytest -q tests/test_app_flask_local_search_api.py tests/test_compare_dbs.py tests/test_compare_db_rows_api.py tests/test_frontend_invalid_flows_browser.py`: `62 passed`
- `pnpm exec eslint static`: passed
- `pnpm exec prettier --check "static/**/*.js" "*.{js,json}"`: passed
