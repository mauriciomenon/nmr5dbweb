# app_flask_search.py
# Backend Flask para pesquisa global e visualização paginada de tabelas em DuckDB.
# Ajuste DB_PATH se o seu arquivo .duckdb estiver em outro local.
from flask import Flask, request, jsonify
import duckdb
from pathlib import Path
from datetime import datetime, date
import decimal

# Caminho padrão para o arquivo DuckDB gerado pelo conversor
DB_PATH = r"C:\mdb2sql_fork\minha.duckdb"

app = Flask(__name__, static_folder="static", static_url_path="")

def connect_db():
    db_file = Path(DB_PATH)
    if not db_file.exists():
        raise FileNotFoundError(f"DuckDB file not found: {DB_PATH}")
    return duckdb.connect(str(db_file))

def serialize_value(v):
    """Converte tipos não-serializáveis para representação JSON-friendly."""
    if v is None:
        return None
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (bytes, bytearray)):
        try:
            return v.decode('utf-8', errors='replace')
        except Exception:
            return repr(v)
    try:
        if isinstance(v, (int, float, str, bool)):
            return v
    except Exception:
        pass
    return str(v)

@app.route("/")
def index():
    return app.send_static_file("index.html")

@app.route("/api/tables", methods=["GET"])
def api_tables():
    try:
        conn = connect_db()
        rows = conn.execute("SHOW TABLES").fetchall()
        conn.close()
        tables = [r[0] for r in rows]
        return jsonify({"tables": tables})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/table", methods=["GET"])
def api_table():
    """
    Retorna paginação e colunas de uma tabela.
    Parâmetros:
      - name (obrigatório): nome da tabela
      - limit (opcional): rows por página (default 50)
      - offset (opcional): offset (default 0)
      - col, q, sort, order (opcional): filtros/ordenação usados na visão por tabela
    """
    table = request.args.get("name")
    if not table:
        return jsonify({"error": "table name required (?name=TABLE_NAME)"}), 400
    try:
        limit = int(request.args.get("limit", 50))
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return jsonify({"error": "limit and offset must be integers"}), 400

    col = request.args.get("col")
    q = request.args.get("q")
    sort = request.args.get("sort")
    order = request.args.get("order", "ASC").upper()
    if order not in ("ASC", "DESC"):
        order = "ASC"

    try:
        conn = connect_db()
        tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
        if table not in tables:
            conn.close()
            return jsonify({"error": f"table not found: {table}"}), 404

        # obter colunas
        cur = conn.execute(f'SELECT * FROM "{table}" LIMIT 0')
        cols = [c[0] for c in cur.description]

        params = []
        where_clause = ""
        if col and q:
            if col not in cols:
                conn.close()
                return jsonify({"error": f"column not found: {col}"}), 400
            where_clause = f'WHERE CAST("{col}" AS VARCHAR) ILIKE ?'
            params.append(f"%{q}%")

        order_clause = ""
        if sort:
            if sort not in cols:
                conn.close()
                return jsonify({"error": f"sort column not found: {sort}"}), 400
            order_clause = f'ORDER BY "{sort}" {order}'

        count_sql = f'SELECT COUNT(*) FROM "{table}"'
        if where_clause:
            count_sql += f" {where_clause}"
        total = conn.execute(count_sql, params).fetchone()[0]

        data_sql = f'SELECT * FROM "{table}"'
        if where_clause:
            data_sql += f" {where_clause}"
        if order_clause:
            data_sql += f" {order_clause}"
        # LIMIT só se limit > 0 (0 significa ilimitado)
        if limit > 0:
            data_sql += f" LIMIT {limit} OFFSET {offset}"
        else:
            # quando ilimitado, ainda aplicamos offset se offset>0
            if offset > 0:
                data_sql += f" OFFSET {offset}"

        rows = conn.execute(data_sql, params).fetchall()
        conn.close()

        # serializar rows
        rows_serial = [[serialize_value(v) for v in row] for row in rows]

        return jsonify({
            "columns": cols,
            "rows": rows_serial,
            "total": total,
            "limit": limit,
            "offset": offset
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/search", methods=["GET"])
def api_search():
    """
    Busca global que retorna LINHAS COMPLETAS por tabela (limitadas por per_table).
    Parâmetros:
      - q (obrigatório): termo a buscar
      - per_table (opcional): máximo de linhas retornadas por tabela (default 25). Use 0 para ilimitado.
      - limit_tables (opcional): máximo de tabelas a escanear (default 100). Use 0 para todas as tabelas.
      - tables (opcional): lista separada por vírgula para limitar escopo
    Resposta:
      { q: "...", scanned_tables: N, results: { table_name: { columns: [...], rows: [[...], ...] } } }
    """
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "query parameter 'q' required"}), 400

    try:
        per_table = int(request.args.get("per_table", 25))
        limit_tables = int(request.args.get("limit_tables", 100))
    except ValueError:
        return jsonify({"error": "per_table and limit_tables must be integers"}), 400

    tables_param = request.args.get("tables")
    requested_tables = [t.strip() for t in tables_param.split(",")] if tables_param else None
    like_param = f"%{q}%"

    results = {}
    scanned = 0
    try:
        conn = connect_db()
        all_tables = [r[0] for r in conn.execute("SHOW TABLES").fetchall()]
        # opcional: filtrar apenas nas tabelas requisitadas
        tables = [t for t in all_tables if (requested_tables is None or t in requested_tables)]
        # limitar tabelas escaneadas: se limit_tables == 0 => sem limite
        if limit_tables > 0:
            tables = tables[:limit_tables]

        for table in tables:
            scanned += 1
            # obter colunas de forma segura
            try:
                cur = conn.execute(f'SELECT * FROM "{table}" LIMIT 0')
                cols = [c[0] for c in cur.description]
            except Exception:
                # pular tabelas problemáticas
                continue

            if not cols:
                continue

            # construir WHERE: CAST(col AS VARCHAR) ILIKE ? para cada coluna
            checks = [f'CAST("{c}" AS VARCHAR) ILIKE ?' for c in cols]
            params = [like_param] * len(cols)
            where_clause = " OR ".join(checks)
            sql = f'SELECT * FROM "{table}" WHERE {where_clause}'
            # se per_table > 0 aplicamos LIMIT
            if per_table > 0:
                sql += f" LIMIT {per_table}"

            try:
                rows = conn.execute(sql, params).fetchall()
            except Exception:
                # se falhar por tipos estranhos, pula tabela
                continue

            if rows:
                # serializar linhas
                rows_serial = [[serialize_value(v) for v in row] for row in rows]
                results[table] = {
                    "columns": cols,
                    "rows": rows_serial
                }

        conn.close()
        return jsonify({"q": q, "results": results, "scanned_tables": scanned})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Dev server
    app.run(host="127.0.0.1", port=5000, debug=True)