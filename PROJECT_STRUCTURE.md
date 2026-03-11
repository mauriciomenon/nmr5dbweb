# Project Structure

## Goal

Map the current product structure in a stable way so future rounds can update this file instead of rediscovering the repo each time.

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
- `docs/`
  - End-user setup and usage guides.
- `artifacts/`
  - Runtime/generated artifacts guidance only. Generated content must stay out of git.
- `tests/`
  - Current focused tests for compare flows.
- `notes/`
  - Working notes. Keep only durable knowledge here.

## Runtime Flow

1. `main.py` starts Flask from `interface/app_flask_local_search.py`.
2. Upload flow accepts `.duckdb`, `.db`, `.sqlite`, `.sqlite3`, `.mdb`, `.accdb`.
3. Access files can be converted by `access_convert.py`.
4. Converted DuckDB files can be indexed by `interface/create_fulltext.py`.
5. Search uses `_fulltext` for DuckDB and ODBC fallback for Access.
6. Compare uses `interface/compare_dbs.py`.
7. Multi-file record tracking uses `interface/find_record_across_dbs.py`.

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
- Generated `.duckdb`, `.db`, `.sqlite`, `.sqlite3`
- Logs, temp files, generated reports, and ad hoc inspection scripts tied to one machine

## Current Architecture Risks

- Main backend file is too large and mixes many responsibilities.
- Search, compare, and conversion use different data models and do not have a single clear contract.
- Frontend client logic is duplicated in `static/app.js`.
- Some docs still point to the student fork and old paths.

## Update Rule

When the architecture changes, update this file first with:

1. new or removed modules
2. flow changes
3. runtime state changes
4. known risks that remain true
