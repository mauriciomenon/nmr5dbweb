#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
batch_analyze_all_dbs.py

Executa a análise por coluna (analyze_single_table_by_column.py) em todos os arquivos de banco
de um diretório, um a um, gravando a saída organizada em subpastas dentro do diretório --outdir.

Modo de operação (simples):
 - Procura recursivamente por arquivos com extensões configuráveis (--extensions).
 - Para cada arquivo encontrado, detecta engine a partir da extensão e chama o script
   tools/analyze_single_table_by_column.py via subprocess, enviando:
     --db <arquivo> --table <tabela> --engine <detected> --outdir "<outdir>\<basename_do_arquivo>"
 - Assim cada banco tem sua própria pasta de saída (facilita agregação posterior).

Requisitos:
 - Ter o script tools/analyze_single_table_by_column.py presente e funcionando no mesmo repo.
 - venv ativado com dependências do analyze_single_table_by_column.py (pyodbc se Access).

Exemplo de uso:
 python tools/batch_analyze_all_dbs.py --db-dir "C:\mdb2sql_fork\import_folder\Bancos atuais" \
   --table "RANGER_SOSTAT" --outdir "C:\mdb2sql_fork\import_folder\Analises" --extensions .accdb .mdb -v

Observações:
 - Se preferir paralelizar, posso adicionar execução concorrente (ThreadPool).
 - O script não tenta reprocessar pastas já existentes com o mesmo nome de arquivo; por padrão sobrescreve.
"""
from pathlib import Path
import argparse
import subprocess
import sys
import shutil

EXT_TO_ENGINE = {
    '.accdb': 'access',
    '.mdb': 'access',
    '.db': 'sqlite',   # cuidado: se for duckdb ajuste manualmente
    '.sqlite': 'sqlite',
    '.sqlite3': 'sqlite',
    '.duckdb': 'duckdb'
}

def detect_engine_from_ext(path: Path, override_engine=None):
    if override_engine:
        return override_engine
    sfx = path.suffix.lower()
    return EXT_TO_ENGINE.get(sfx, 'sqlite')

def gather_files(db_dir: Path, exts):
    files = []
    for ext in exts:
        files += list(db_dir.rglob(f"*{ext}"))
    # remover duplicados e ordenar
    unique = sorted({f.resolve(): f for f in files}.values(), key=lambda p: p.stat().st_mtime)
    return unique

def run_analyze_for_file(py_exe, analyze_script, db_file: Path, table: str, engine: str, outdir: Path, top:int, distinct_cap:int, verbose:bool):
    # cria outdir específico para esse arquivo
    db_basename = db_file.stem
    per_out = outdir / db_basename
    per_out.mkdir(parents=True, exist_ok=True)
    cmd = [
        py_exe, str(analyze_script),
        "--db", str(db_file),
        "--table", table,
        "--engine", engine,
        "--outdir", str(per_out),
        "--top", str(top),
        "--distinct-cap", str(distinct_cap)
    ]
    if verbose:
        cmd.append("-v")
        print("[cmd]"," ".join(cmd))
    # executar e esperar
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return res.returncode, res.stdout

def parse_args():
    p = argparse.ArgumentParser(description="Executar analyze_single_table_by_column.py em lote para múltiplos arquivos.")
    p.add_argument("--db-dir", required=True, help="Diretório contendo os arquivos de banco (recursivo).")
    p.add_argument("--table", required=True, help="Nome da tabela a analisar em cada banco.")
    p.add_argument("--outdir", required=True, help="Diretório base onde serão gravadas as pastas de saída por banco.")
    p.add_argument("--extensions", nargs='*', default=['.accdb','.mdb','.db','.sqlite','.duckdb'], help="Extensões a procurar.")
    p.add_argument("--python-exe", default=sys.executable, help="Executável Python a usar (por padrão o atual).")
    p.add_argument("--analyze-script", default="tools/analyze_single_table_by_column.py", help="Caminho para o script de análise por arquivo.")
    p.add_argument("--top", type=int, default=25, help="Top N valores por coluna a gerar por banco.")
    p.add_argument("--distinct-cap", type=int, default=200000, help="Cap de distinct para cada execução.")
    p.add_argument("-v","--verbose", action="store_true")
    return p.parse_args()

def main():
    args = parse_args()
    db_dir = Path(args.db_dir)
    if not db_dir.exists():
        print("Diretório não encontrado:", db_dir); return 1
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    exts = [e if e.startswith('.') else '.'+e for e in args.extensions]

    files = gather_files(db_dir, exts)
    if not files:
        print("Nenhum arquivo encontrado com as extensões fornecidas em", db_dir); return 1

    analyze_script = Path(args.analyze_script)
    if not analyze_script.exists():
        print("Script de análise não encontrado:", analyze_script); return 1

    total = len(files)
    failed = []
    for idx, f in enumerate(files, start=1):
        engine = detect_engine_from_ext(f)
        if args.verbose:
            print(f"[{idx}/{total}] Processando {f} (engine={engine})")
        code, out = run_analyze_for_file(args.python_exe, analyze_script, f, args.table, engine, outdir, args.top, args.distinct_cap, args.verbose)
        if args.verbose:
            print(out)
        if code != 0:
            print(f"[erro] falha no arquivo {f.name} (exit {code})")
            failed.append((f.name, out))
    print(f"\nConcluído. Total arquivos: {total}. Falhas: {len(failed)}")
    if failed:
        print("Arquivos com falha (nome e trecho de log):")
        for n,log in failed:
            print(" -", n, " -> log (primeiros 200 chars):\n", log[:200].replace("\n"," "))
    return 0

if __name__ == "__main__":
    sys.exit(main())