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
