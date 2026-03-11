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

## Operator Notes For Next Conversation

- Read `PROJECT_STRUCTURE.md` first
- Read `ROUND_STATUS.md` second
- Read `RECOVERY_BACKLOG.md` for deferred work
- Keep changes minimal and behavior-preserving
- Use the project-local `.venv` only; do not rely on `/Users/menon/git/.venv`
- Do not start broad frontend refactors before deciding whether the next slice is `static/app.js` structure cleanup or Python debt baseline reduction
