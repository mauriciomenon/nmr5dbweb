import duckdb
import logging
from pathlib import Path

DB = str(Path(__file__).resolve().parent.parent / "artifacts" / "minha.duckdb")
logger = logging.getLogger(__name__)

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
        failed = []
        for t in tables:
            try:
                table_row = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()
                if table_row is None:
                    raise RuntimeError("count query returned no row")
                cnt_table = int(table_row[0])
            except Exception as e:
                logger.warning("Could not read table %s: %s", t, e)
                print(f"  Could not read table {t}: table_count_failed")
                failed.append((t, "table_count_failed"))
                continue
            try:
                indexed_row = conn.execute(
                    "SELECT COUNT(*) FROM _fulltext WHERE table_name = ?",
                    [t],
                ).fetchone()
                cnt_indexed = int(indexed_row[0]) if indexed_row is not None else 0
            except Exception as e:
                logger.warning("Could not read _fulltext progress for %s: %s", t, e)
                print(f"  Could not read _fulltext progress for {t}: fulltext_count_failed")
                failed.append((t, "fulltext_count_failed"))
                continue
            if cnt_indexed < cnt_table:
                missing.append((t, cnt_table, cnt_indexed))
        if not missing and not failed:
            print("All tables appear fully indexed (or no user tables found).")
        if missing:
            print("Tables not yet fully indexed (table, table_rows, indexed_rows):")
            for t, total, idx in missing:
                print(f"  {t}: {idx} / {total} indexed (missing {total-idx})")
            print(f"\nTotal tables with missing rows: {len(missing)}")
        if failed:
            print("Tables that could not be checked:")
            for t, error in failed:
                print(f"  {t}: {error}")
            print(f"\nTotal tables with check errors: {len(failed)}")
    finally:
        conn.close()

if __name__ == '__main__':
    main()
