#!/usr/bin/env python3
"""Run end-to-end local validation pipeline for dataset artifacts.

Pipeline:
1) Prepare canonical dataset artifacts (DuckDB/SQLite + manifest)
2) Optionally run benchmark flows on generated artifacts
3) Emit a compact pipeline status markdown for operator use
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path


def _run_step(cmd: list[str], title: str, repo_root: Path) -> None:
    print(f"[pipeline] {title}: {' '.join(cmd)}")
    env = dict(os.environ)
    current_pythonpath = env.get("PYTHONPATH", "").strip()
    repo_root_str = str(repo_root)
    if current_pythonpath:
        env["PYTHONPATH"] = f"{repo_root_str}{os.pathsep}{current_pythonpath}"
    else:
        env["PYTHONPATH"] = repo_root_str
    proc = subprocess.run(cmd, check=False, env=env, cwd=str(repo_root))
    if proc.returncode != 0:
        raise RuntimeError(f"step failed ({title}), exit={proc.returncode}")


def _build_status_markdown(
    manifest_path: Path,
    status_path: Path,
    benchmark_summary_path: Path | None,
) -> None:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = data.get("items", [])
    total = len(items)
    duck_ok = sum(1 for item in items if item.get("duckdb_ok"))
    sqlite_ok = sum(1 for item in items if item.get("sqlite_ok"))
    suffix_counter = Counter(str(item.get("source_suffix", "")).lower() for item in items)

    duck_fail = [item for item in items if not item.get("duckdb_ok")]
    sqlite_fail = [item for item in items if item.get("duckdb_ok") and not item.get("sqlite_ok")]

    lines = [
        "# Validation Pipeline Status",
        "",
        f"- total_sources: {total}",
        f"- duckdb_ok: {duck_ok}",
        f"- sqlite_ok: {sqlite_ok}",
        "",
        "## Sources By Suffix",
        "",
    ]
    for suffix in sorted(suffix_counter):
        lines.append(f"- {suffix or '(none)'}: {suffix_counter[suffix]}")

    if duck_fail:
        lines.extend([
            "",
            "## DuckDB Conversion Failures",
            "",
        ])
        for item in duck_fail[:20]:
            lines.append(
                f"- {item.get('id')}: {item.get('duckdb_msg') or 'failed'}"
            )

    if sqlite_fail:
        lines.extend([
            "",
            "## SQLite Materialization Failures",
            "",
        ])
        for item in sqlite_fail[:20]:
            lines.append(
                f"- {item.get('id')}: {item.get('sqlite_msg') or 'failed'}"
            )

    lines.extend([
        "",
        "## Outputs",
        "",
        f"- manifest: `{manifest_path}`",
        f"- status: `{status_path}`",
    ])
    if benchmark_summary_path is not None and benchmark_summary_path.exists():
        lines.append(f"- benchmark_summary: `{benchmark_summary_path}`")

    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[pipeline] status markdown generated: {status_path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run local dataset validation pipeline (prepare + benchmark + summary)."
    )
    parser.add_argument(
        "--input-dir",
        default="output",
        help="Input source folder (default: output)",
    )
    parser.add_argument(
        "--out-root",
        default="artifacts/validation",
        help="Output root folder (default: artifacts/validation)",
    )
    parser.add_argument(
        "--skip-benchmark",
        action="store_true",
        help="Skip benchmark step and generate only manifest/status",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    py = sys.executable

    prepare_script = repo_root / "tools" / "prepare_validation_artifacts.py"
    benchmark_script = repo_root / "tools" / "benchmark_validation_flows.py"
    reports_dir = (repo_root / args.out_root / "reports").resolve()
    manifest_path = reports_dir / "dataset_manifest.json"
    status_path = reports_dir / "pipeline_status.md"
    benchmark_summary_path = reports_dir / "benchmark_summary.md"
    benchmark_csv_path = reports_dir / "benchmark_times.csv"

    _run_step(
        [
            py,
            str(prepare_script),
            "--input-dir",
            args.input_dir,
            "--out-root",
            args.out_root,
        ],
        "prepare_artifacts",
        repo_root,
    )

    if not args.skip_benchmark:
        _run_step(
            [
                py,
                str(benchmark_script),
                "--manifest",
                str(manifest_path),
                "--out-csv",
                str(benchmark_csv_path),
                "--out-md",
                str(benchmark_summary_path),
            ],
            "benchmark_flows",
            repo_root,
        )

    _build_status_markdown(
        manifest_path=manifest_path,
        status_path=status_path,
        benchmark_summary_path=None if args.skip_benchmark else benchmark_summary_path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
