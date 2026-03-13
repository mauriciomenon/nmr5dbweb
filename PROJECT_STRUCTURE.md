# Project Structure

## Goal

Map the current product structure in a stable way so future rounds can update this file instead of rediscovering the repo each time.

## Latest Snapshot (2026-03-13)

- Product PR context for active development is on `mauriciomenon/nmr5dbweb` PR `#2` (`codex/dev` -> `master`).
- The `allysonalmeidaa/mdb2sql_fork` PR `#2` context is not the active product PR flow.
- Compare upload flow now tolerates invalid/non-JSON upload responses without crashing the client logic (`static/compare_dbs_upload.js`).
- Windows Access smoke path now removes temporary output files on failure states (`tools/windows_access_smoke.py`).

## Top Level

- `main.py`
  - Main CLI entrypoint for the local Flask server.
- `interface/`
  - Main backend for upload, selection, search, compare, indexing, and record tracking.
- `static/`
  - Web UI assets and pages.
- `converters/`
  - Access to DuckDB conversion alternatives and benchmarks.
- `tools/`
  - Analysis, reporting, and record tracking support scripts.
  - Includes validation pipeline scripts:
    - `tools/prepare_validation_artifacts.py`
    - `tools/benchmark_validation_flows.py`
  - Includes operator compare report automation:
    - `tools/auto_compare_report.py` (interactive compare report exporter to HTML/MD/TXT)
- `docs/`
  - End-user setup and usage guides.
- `artifacts/`
  - Runtime/generated artifacts guidance only. Generated content must stay out of git.
  - Includes local validation pipeline outputs under `artifacts/validation/`:
    - `input/`
    - `derived/duckdb/`
    - `derived/sqlite/`
    - `reports/`
- `output/`
  - Local validation area with real operator samples and smoke fixtures.
  - Useful for manual proof-of-use rounds, but not part of the product runtime contract.
- `tests/`
  - Current focused tests for compare flows.
- `bkp_limpeza/`
  - Local ignored backup area for files removed from the product path during safe cleanup rounds.

## Runtime Flow

1. `main.py` starts Flask from `interface/app_flask_local_search.py`.
2. Upload flow accepts `.duckdb`, `.db`, `.sqlite`, `.sqlite3`, `.mdb`, `.accdb`.
3. Access files can be converted by `access_convert.py`.
4. Converted DuckDB files can be indexed by `interface/create_fulltext.py`.
5. Search uses `_fulltext` for DuckDB and ODBC fallback for Access.
6. Compare uses `interface/compare_dbs.py`.
7. Multi-file record tracking uses `interface/find_record_across_dbs.py`.
8. Operator compare report automation uses `tools/auto_compare_report.py`, which can resolve Access/DuckDB/SQLite inputs and export human-readable artifacts under `documentos/reports/`.

## Product Decisions

- Keep support for `DuckDB`, `SQLite`, and `Access (.mdb/.accdb)`.
- Keep DuckDB as the primary engine for:
  - keyed compare
  - `_fulltext` search
  - table browsing in the main UI
  - converted Access operational flow
- Keep the current fast keyed compare behavior as a protected product feature.
- If a more detailed compare/report layer is added later, it must not degrade the current fast compare path.
- SQLite support is intentionally retained because the product can generate or receive the same logical DB in that format too.
- Access direct support remains useful for conversion and tracking, but the main compare path is DuckDB-first.

## Main Modules

- `interface/app_flask_local_search.py`
  - Product backend.
  - Owns config state, upload state, search routes, compare routes, and tracking routes.
- `interface/compare_dbs.py`
  - Compare engine for DuckDB tables.
- `interface/create_fulltext.py`
  - Builds or resumes `_fulltext`.
- `interface/find_record_across_dbs.py`
  - Scans many DB files and checks for record presence by filters.
- `access_convert.py`
  - Access to DuckDB conversion entrypoint.
- `interface/utils.py`
  - Shared normalization and serialization helpers.
- `tools/auto_compare_report.py`
  - Compare report automation with interactive HTML controls and companion MD/TXT outputs.

## Product Surfaces

- `static/index.html`
  - Main search and upload flow.
- `static/compare_dbs.html`
  - Two-file compare flow.
- `static/track_record.html`
  - Track a record across many DB files.
- `static/app.js`
  - Main client logic. Currently too large and has duplicated function blocks.

## Runtime State That Must Stay Out Of Git

- `interface/config.json`
  - Local machine state only.
- `interface/uploads/`
  - Uploaded and converted DB files.
- `bkp_limpeza/`
  - Local cleanup backup only.
- Generated `.duckdb`, `.db`, `.sqlite`, `.sqlite3`
- Logs, temp files, generated reports, and ad hoc inspection scripts tied to one machine

## Current Architecture Risks

- Main backend file is too large and mixes many responsibilities.
- Search, compare, and conversion use different data models and do not have a single clear contract.
- Frontend duplication risk was reduced, but the client layer is still spread across large operational files.
- Some docs still point to the student fork and old paths.
- The main UI still works around a single active DB selection model in the backend.
- SQLite is accepted by the product, but the main UI/backend contract around it still needs explicit hardening.
- Safe cleanup is now proving use before removal; unrelated notes and the old simplified Flask backend are no longer part of the product path.
- The report automation script has grown into a key operator path and now needs disciplined regression coverage to avoid UI/control drift.

## Reporting Notes

- The current compare UI already provides useful triage-level reporting:
  - table overview
  - keyed row diff
  - changed-column summaries
  - record tracking across many DB files
- The dedicated compare report automation now also provides:
  - multi-engine input awareness (Access, DuckDB, SQLite)
  - interactive HTML quick filters and sorting controls
  - synchronized Markdown and text outputs for non-browser review
  - source metadata and engine-usage visibility for auditability
- These reports are already useful for spotting:
  - unexpected row additions/removals
  - wrong categorical values
  - field-level drift across versions
  - engine- or file-level access failures
- The example report patterns provided by the user suggest a valuable next reporting layer:
  - grouped anomaly sections
  - field-focused difference emphasis
  - easier visual detection of semantic errors in rows that still "exist"
- Any future reporting work should build on the current compare output, not replace or slow down the fast compare path.

## Update Rule

When the architecture changes, update this file first with:

1. new or removed modules
2. flow changes
3. runtime state changes
4. known risks that remain true
