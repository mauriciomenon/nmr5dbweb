# Validation Reports

This folder stores reproducible validation outputs generated from local DB files.

## Inputs and outputs

- input source folder: `output/`
- canonical copies: `artifacts/validation/input/`
- canonical duckdb: `artifacts/validation/derived/duckdb/`
- canonical sqlite: `artifacts/validation/derived/sqlite/`

## Generate canonical DB artifacts

```bash
uv run python tools/prepare_validation_artifacts.py \
  --input-dir output \
  --out-root artifacts/validation
```

Main output:

- `dataset_manifest.json`
- `compare_report_example.json`

## Run timing benchmark

```bash
uv run python tools/benchmark_validation_flows.py \
  --manifest artifacts/validation/reports/dataset_manifest.json \
  --out-csv artifacts/validation/reports/benchmark_times.csv \
  --out-md artifacts/validation/reports/benchmark_summary.md
```

Main outputs:

- `benchmark_times.csv`
- `benchmark_summary.md`

## Notes

- Access conversion tries `pyodbc`/`mdbtools` first, then falls back to `access-parser` when available.
- Compare API fast path is duckdb-only today; sqlite/access should be converted to duckdb before compare.
- If conversion fails for a source file, the manifest records the failure and the pipeline continues.
