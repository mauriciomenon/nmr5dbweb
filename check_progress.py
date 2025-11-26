import duckdb
from pathlib import Path

DB = r"C:\mdb2sql_fork\minha.duckdb"

def main():
    dbfile = Path(DB)
    if not dbfile.exists():
        print("DuckDB file not found:", DB)
        return
    conn = duckdb.connect(DB)
    try:
        tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
        # ignore internal/system tables and _fulltext itself
        tables = [t for t in tables if not (t.lower().startswith('msys') or t.lower().startswith('sqlite_') or t.lower().startswith('duckdb_') or t.lower() == '_fulltext')]
        print(f"Found {len(tables)} user tables to check.")
        missing = []
        for t in tables:
            try:
                cnt_table = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            except Exception as e:
                print(f"  Could not read table {t}: {e}")
                continue
            try:
                cnt_indexed = conn.execute("SELECT COUNT(*) FROM _fulltext WHERE table_name = ?", [t]).fetchone()[0]
            except Exception:
                cnt_indexed = 0
            if cnt_indexed < cnt_table:
                missing.append((t, cnt_table, cnt_indexed))
        if not missing:
            print("All tables appear fully indexed (or no user tables found).")
        else:
            print("Tables not yet fully indexed (table, table_rows, indexed_rows):")
            for t, total, idx in missing:
                print(f"  {t}: {idx} / {total} indexed (missing {total-idx})")
            print(f"\nTotal tables with missing rows: {len(missing)}")
    finally:
        conn.close()

if __name__ == '__main__':
    main()