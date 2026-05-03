from interface.app_flask_local_search import api_search_duckdb, cfg, get_db_path

if __name__ == "__main__":
    q = "AUX_UNIDAD"
    db_path = get_db_path()
    if not db_path:
        raise SystemExit("db_path nao configurado")
    res = api_search_duckdb(
        db_path,
        q,
        per_table=1000000,
        candidate_limit=1000000,
        total_limit=1000000,
        token_mode="any",
        min_score=70,
    )
    print("priority_tables:", cfg.get("priority_tables"))
    print("candidate_count:", res.get("candidate_count"), "returned_count:", res.get("returned_count"))
    print("tables in order (primeiras 10):")
    for name in list(res.get("results", {}).keys())[:10]:
        print(" -", name)
