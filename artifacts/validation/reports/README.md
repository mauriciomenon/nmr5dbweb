# Validation Reports

This folder stores reproducible validation outputs generated from local DB files.

## Inputs and outputs

- input source folder: `output/`
- canonical copies: `artifacts/validation/input/`
- canonical duckdb: `artifacts/validation/derived/duckdb/`
- canonical sqlite: `artifacts/validation/derived/sqlite/`

## Generate canonical DB artifacts

```bash
uv run python tools/prepare_validation_artifacts.py
```

Main output:

- `dataset_manifest.json`

## Run timing benchmark

```bash
uv run python tools/benchmark_validation_flows.py
```

Main outputs:

- `benchmark_times.csv`
- `benchmark_summary.md`

## Notes

- Access conversion depends on local drivers/tools (`pyodbc` or `mdbtools`).
- If Access conversion fails for a source file, the manifest records the failure and continues.
