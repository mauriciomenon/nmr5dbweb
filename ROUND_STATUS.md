# Round Status

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

- Focused backend API validation is now green in the project-local venv.
- The upload and search paths now fail earlier and more explicitly on bad input.
- Optional backend dependencies are now guarded without silent fallback.

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
