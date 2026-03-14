#!/usr/bin/env python3

import argparse
import duckdb
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List

try:
    from converters.common import (
        extract_date_from_filename,
        list_access_files,
        validate_cli_input,
    )
except ModuleNotFoundError:
    from common import extract_date_from_filename, list_access_files, validate_cli_input

_COMPILED_JAVA_HELPERS = set()


def get_jackcess_classpath():
    base_dir = Path(__file__).resolve().parent.parent / "temp"
    jars = [
        base_dir / "jackcess-4.0.5.jar",
        base_dir / "commons-lang3-3.14.0.jar",
        base_dir / "commons-logging-1.3.0.jar",
    ]
    return os.pathsep.join(str(j) for j in jars)


def _compile_java_helper_once(temp_dir: Path, class_name: str, java_code: str, classpath: str):
    if class_name in _COMPILED_JAVA_HELPERS:
        return
    java_file = temp_dir / f"{class_name}.java"
    java_file.write_text(java_code)
    subprocess.run(
        ["javac", "-cp", classpath, str(java_file)],
        check=True,
        capture_output=True,
    )
    _COMPILED_JAVA_HELPERS.add(class_name)


def get_mdb_tables_jackcess(mdb_file: Path) -> List[str]:
    try:
        classpath = get_jackcess_classpath()
        java_code = """
import com.healthmarketscience.jackcess.*;
import java.io.*;
public class ListTables {
    public static void main(String[] args) throws Exception {
        if (args.length < 1) throw new IllegalArgumentException("missing mdb path");
        try (Database db = DatabaseBuilder.open(new File(args[0]))) {
            for (String tableName : db.getTableNames()) {
                System.out.println(tableName);
            }
        }
    }
}
"""
        temp_dir = Path("/tmp/mdb2sql_jackcess")
        temp_dir.mkdir(exist_ok=True)

        _compile_java_helper_once(temp_dir, "ListTables", java_code, classpath)

        result = subprocess.run(
            ["java", "-cp", f"{classpath}{os.pathsep}{temp_dir}", "ListTables", str(mdb_file)],
            capture_output=True,
            text=True,
            check=True,
        )

        tables = [t.strip() for t in result.stdout.split("\n") if t.strip()]
        return tables
    except subprocess.CalledProcessError as e:
        print(f"Error listing tables: {e}")
        print(f"stderr: {e.stderr}")
        return []
    except FileNotFoundError:
        print("Java not found. Install JDK.")
        sys.exit(1)


def export_table_jackcess(mdb_file: Path, table_name: str, output_csv: Path) -> bool:
    try:
        classpath = get_jackcess_classpath()
        java_code = """
import com.healthmarketscience.jackcess.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
public class ExportTable {{
    public static void main(String[] args) throws Exception {{
        if (args.length < 3) throw new IllegalArgumentException("missing args");
        String dbPath = args[0];
        String outPath = args[1];
        String tableName = args[2];
        try (Database db = DatabaseBuilder.open(new File(dbPath));
             PrintWriter writer = new PrintWriter(
                 new OutputStreamWriter(new FileOutputStream(outPath), StandardCharsets.UTF_8)
             )) {{
            Table table = db.getTable(tableName);
            java.util.List columns = table.getColumns();
            boolean first = true;
            for (Object col : columns) {{
                if (!first) writer.print(",");
                writer.print(((Column)col).getName());
                first = false;
            }}
            writer.println();
            for (Row row : table) {{
                first = true;
                for (Object col : columns) {{
                    if (!first) writer.print(",");
                    Object value = row.get(((Column)col).getName());
                    if (value != null) {{
                        String str = value.toString().replace("\"", "\"\"");
                        if (str.contains(",") || str.contains("\"")) {{
                            writer.print("\"" + str + "\"");
                        }} else {{
                            writer.print(str);
                        }}
                    }}
                    first = false;
                }}
                writer.println();
            }}
        }}
    }}
}}
"""
        temp_dir = Path("/tmp/mdb2sql_jackcess")
        temp_dir.mkdir(exist_ok=True)

        _compile_java_helper_once(temp_dir, "ExportTable", java_code, classpath)

        subprocess.run(
            [
                "java",
                "-cp",
                f"{classpath}{os.pathsep}{temp_dir}",
                "ExportTable",
                str(mdb_file),
                str(output_csv),
                table_name,
            ],
            check=True,
            capture_output=True,
        )

        return True
    except subprocess.CalledProcessError as e:
        print(f"Error exporting table {table_name}: {e}")
        return False


def import_to_duckdb(
    mdb_file: Path,
    duckdb_file: Path,
    file_date: Optional[str] = None,
):
    print(f"\nProcessing: {mdb_file.name}")

    if not file_date:
        file_date = extract_date_from_filename(mdb_file.name)

    if not file_date:
        print(f"WARNING: Could not extract date from {mdb_file.name}")
        file_date = datetime.now().strftime("%Y-%m-%d")

    print(f"Date extracted: {file_date}")

    tables = get_mdb_tables_jackcess(mdb_file)
    if not tables:
        print("No tables found")
        return

    print(f"Tables found: {len(tables)}")

    conn = duckdb.connect(str(duckdb_file))

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS _metadata (
            import_id INTEGER PRIMARY KEY,
            source_file VARCHAR,
            file_date DATE,
            import_timestamp TIMESTAMP,
            table_name VARCHAR,
            row_count INTEGER
        )
    """
    )

    conn.execute("CREATE SEQUENCE IF NOT EXISTS seq_import_id START 1")

    import_timestamp = datetime.now()
    temp_dir = Path("/tmp/mdb2sql")
    temp_dir.mkdir(exist_ok=True)

    for table in tables:
        print(f"  Importing: {table}...", end=" ", flush=True)

        csv_file = temp_dir / f"{table}.csv"

        if not export_table_jackcess(mdb_file, table, csv_file):
            print("FAILED")
            continue

        if csv_file.stat().st_size == 0:
            print("EMPTY")
            csv_file.unlink()
            continue

        base_name = re.sub(r"[^A-Za-z0-9_]", "_", str(table)).strip("_") or "table"
        source_key = str(mdb_file.resolve()).replace("\\", "/")
        table_suffix = hashlib.sha1(f"{source_key}:{table}".encode("utf-8")).hexdigest()[:8]
        table_with_date = f"{base_name}_{table_suffix}_{file_date.replace('-', '')}"

        try:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS "{table_with_date}" AS
                SELECT * FROM read_csv_auto(?,
                    header=true,
                    sample_size=100000
                )
            """,
                [str(csv_file)],
            )

            result = conn.execute(f'SELECT COUNT(*) FROM "{table_with_date}"').fetchone()
            row_count = result[0] if result else 0

            conn.execute(
                """
                INSERT INTO _metadata
                (import_id, source_file, file_date, import_timestamp, table_name, row_count)
                VALUES (nextval('seq_import_id'), ?, ?, ?, ?, ?)
            """,
                [mdb_file.name, file_date, import_timestamp, table_with_date, row_count],
            )

            print(f"OK ({row_count} rows)")

        except Exception as e:
            print(f"ERROR: {e}")
        finally:
            csv_file.unlink(missing_ok=True)

    conn.close()
    print(f"\nImport completed: {duckdb_file}")


def batch_import(input_dir: Path, duckdb_file: Path):
    try:
        mdb_files = list_access_files(input_dir)
    except Exception as e:
        print(f"Error accessing input directory {input_dir}: {e}")
        return

    if not mdb_files:
        print(f"No MDB/ACCDB files found in {input_dir}")
        return

    print(f"\n{'='*60}")
    print(f"Found {len(mdb_files)} files to process")
    print(f"{'='*60}")

    for i, mdb_file in enumerate(mdb_files, 1):
        print(f"\n[{i}/{len(mdb_files)}]", end=" ")
        import_to_duckdb(mdb_file, duckdb_file)


def main():
    parser = argparse.ArgumentParser(
        description="Convert MDB/ACCDB to DuckDB using Jackcess",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Input MDB/ACCDB file or directory for batch",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("database.duckdb"),
        help="Output DuckDB file (default: database.duckdb)",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Process all MDB/ACCDB files in --input directory",
    )

    args = parser.parse_args()

    input_error = validate_cli_input(args.input, args.batch)
    if input_error == "missing_input":
        parser.print_help()
        sys.exit(1)
    if input_error:
        print(input_error)
        sys.exit(1)
    if args.batch:
        batch_import(args.input, args.output)
    else:
        import_to_duckdb(args.input, args.output)


if __name__ == "__main__":
    main()
