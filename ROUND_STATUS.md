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
