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

- `static/app.js` contains duplicated logic blocks
- Backend responsibilities are concentrated in one large Flask file
- Search and compare use different models and are hard to reason about together
- Test environment is not yet reproducible from a clean machine

## Setup Status

- Clean Python setup now uses `uv`
- Use `requirements.txt` for runtime
- Use `requirements-dev.txt` for runtime plus validation tools
- Focused compare tests pass in a clean `uv` venv
- `ruff` and `ty` still expose broad existing debt outside the setup slice

## Operator Notes For Next Conversation

- Read `PROJECT_STRUCTURE.md` first
- Read `ROUND_STATUS.md` second
- Read `RECOVERY_BACKLOG.md` for deferred work
- Keep changes minimal and behavior-preserving
- Do not start refactors before closing the zero-state cleanup
