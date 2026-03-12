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
