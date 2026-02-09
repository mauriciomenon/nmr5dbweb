# MDB2SQL Converters

This folder contains standalone command-line converters and benchmarking tools
for Microsoft Access (MDB/ACCDB) to DuckDB.

## Layout

- `convert_mdbtools.py`  – CLI converter using the `mdbtools` command line tools (Linux/macOS).
- `convert_jackcess.py`  – CLI converter using the Jackcess Java library.
- `convert_pyaccess_parser.py` – Pure Python converter using `access-parser`.
- `convert_pyodbc.py`    – Windows-only converter using `pypyodbc` + Access Database Engine.
- `benchmark.py`         – runs all converters against a folder of MDB/ACCDB files.
- `test_implementations.sh` – small shell script to manually time each converter.

All scripts expect to be executed from the project root, e.g.:

```bash
python converters/convert_mdbtools.py --input import_folder/DB2_20_11_2013.mdb --output artifacts/db2_mdbtools.duckdb
python converters/benchmark.py import_folder
```
