#!/usr/bin/env python3
"""
MDB to DuckDB Converter using access-parser library

Pure Python implementation for converting Microsoft Access MDB/ACCDB files
 to DuckDB format using the access-parser library. No external system
 dependencies beyond Python packages.
"""

import argparse
import re
import sys
import traceback
from pathlib import Path
from datetime import datetime

try:
    import access_parser as ap
    import duckdb
except ImportError as e:
    print(f"Error: Missing required library: {e}")
    print("Install with: pip install access-parser duckdb")
    sys.exit(1)


def extract_date_from_filename(filename):
    patterns = [
        r"(\d{2})_(\d{2})_(\d{4})",
        r"(\d{4})_(\d{2})_(\d{2})",
        r"(\d{2})-(\d{2})-(\d{4})",
        r"(\d{4})-(\d{2})-(\d{2})",
    ]

    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            parts = match.groups()
            if len(parts[0]) == 4:
                year, month, day = parts
            else:
                day, month, year = parts

            try:
                date_obj = datetime(int(year), int(month), int(day))
                return date_obj.strftime("%Y-%m-%d")
            except ValueError:
                continue

    return None


def sanitize_table_name(name):
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if name and name[0].isdigit():
        name = "T_" + name
    return name


def convert_mdb_to_duckdb(mdb_path, duckdb_path, batch_mode=False):
    mdb_file = Path(mdb_path)

    if not mdb_file.exists():
        print(f"Error: File not found: {mdb_path}")
        return False

    print(f"\nProcessing: {mdb_file.name}")

    date_str = extract_date_from_filename(mdb_file.name)
    if date_str:
        print(f"Date extracted: {date_str}")
        date_suffix = date_str.replace("-", "")
    else:
        print("Warning: Could not extract date from filename")
        date_suffix = datetime.now().strftime("%Y%m%d")

    conn = None
    try:
        print("Opening MDB file...")
        db = ap.AccessParser(str(mdb_file))

        try:
            table_names = list(db.catalog.keys())
        except Exception:
            tables_obj = getattr(db, "tables", None)
            if isinstance(tables_obj, dict):
                table_names = [str(name) for name in tables_obj.keys()]
            else:
                table_names = []

        print(f"Tables found: {len(table_names)}")

        conn = duckdb.connect(str(duckdb_path))

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS _metadata (
                import_date TIMESTAMP,
                source_file VARCHAR,
                table_name VARCHAR,
                row_count INTEGER,
                date_suffix VARCHAR
            )
        """
        )

        total_tables = 0
        total_rows = 0

        for table_name in table_names:
            try:
                sanitized_name = sanitize_table_name(table_name)
                final_table_name = f"{sanitized_name}_{date_suffix}"

                if not batch_mode:
                    print(f"  Importing: {table_name}...", end=" ", flush=True)

                table_data = db.parse_table(table_name)

                if not table_data:
                    if not batch_mode:
                        print("OK (0 rows)")
                    conn.execute(
                        "INSERT INTO _metadata VALUES (?, ?, ?, ?, ?)",
                        [
                            datetime.now(),
                            mdb_file.name,
                            final_table_name,
                            0,
                            date_suffix,
                        ],
                    )
                    continue

                column_names = list(table_data.keys())
                if not column_names:
                    if not batch_mode:
                        print("OK (0 rows)")
                    conn.execute(
                        "INSERT INTO _metadata VALUES (?, ?, ?, ?, ?)",
                        [
                            datetime.now(),
                            mdb_file.name,
                            final_table_name,
                            0,
                            date_suffix,
                        ],
                    )
                    continue

                sanitized_columns = [sanitize_table_name(col) for col in column_names]

                row_count = len(table_data[column_names[0]])

                if row_count == 0:
                    if not batch_mode:
                        print("OK (0 rows)")
                    conn.execute(
                        "INSERT INTO _metadata VALUES (?, ?, ?, ?, ?)",
                        [
                            datetime.now(),
                            mdb_file.name,
                            final_table_name,
                            0,
                            date_suffix,
                        ],
                    )
                    continue

                conn.execute(f'DROP TABLE IF EXISTS "{final_table_name}"')

                column_defs = ", ".join(
                    [f'"{col}" VARCHAR' for col in sanitized_columns]
                )
                conn.execute(f'CREATE TABLE "{final_table_name}" ({column_defs})')

                placeholders = ", ".join(["?" for _ in sanitized_columns])
                rows_data = [
                    [table_data[col][i] for col in column_names]
                    for i in range(row_count)
                ]
                conn.executemany(
                    f'INSERT INTO "{final_table_name}" VALUES ({placeholders})',
                    rows_data,
                )

                conn.execute(
                    "INSERT INTO _metadata VALUES (?, ?, ?, ?, ?)",
                    [
                        datetime.now(),
                        mdb_file.name,
                        final_table_name,
                        row_count,
                        date_suffix,
                    ],
                )

                if not batch_mode:
                    print(f"OK ({row_count} rows)")

                total_tables += 1
                total_rows += row_count

            except Exception as e:
                if not batch_mode:
                    print(f"ERROR: {str(e)}")
                continue

        if conn is not None:
            conn.close()

        print("\nSummary:")
        print(f"  Tables imported: {total_tables}")
        print(f"  Total rows: {total_rows}")
        print(f"  Output: {duckdb_path}")

        return True

    except Exception as e:
        print(f"Error processing MDB file: {e}")
        traceback.print_exc()
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Convert Microsoft Access MDB files to DuckDB using access-parser",
    )
    parser.add_argument("--input", "-i", required=True, help="Input MDB file path")
    parser.add_argument("--output", "-o", required=True, help="Output DuckDB file path")
    parser.add_argument(
        "--batch",
        "-b",
        action="store_true",
        help="Batch mode (less verbose output)",
    )

    args = parser.parse_args()

    success = convert_mdb_to_duckdb(args.input, args.output, args.batch)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
