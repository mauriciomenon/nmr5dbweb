#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from tools.auto_compare_report import (
    _resolve_default_dirs,
    list_candidate_files,
    run_compare_pipeline,
    suggest_two_sources,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate minimal compare report using two latest supported sources "
            "in documentos/ when --db1/--db2 are not provided."
        )
    )
    parser.add_argument("--docs-dir", default="", help="Documentos directory")
    parser.add_argument("--reports-dir", default="", help="Reports directory")
    parser.add_argument("--db1", default="", help="Source A path")
    parser.add_argument("--db2", default="", help="Source B path")
    return parser


def _resolve_sources(args, docs_dir: Path) -> tuple[Path, Path]:
    if args.db1 and args.db2:
        src_a = Path(args.db1).expanduser().resolve()
        src_b = Path(args.db2).expanduser().resolve()
        if src_a == src_b:
            raise ValueError("db1 and db2 cannot be equal")
        return src_a, src_b

    items = list_candidate_files(docs_dir)
    first, second = suggest_two_sources(items)
    return first.path, second.path


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    project_root = Path(__file__).resolve().parents[1]
    default_docs, default_reports = _resolve_default_dirs(project_root)
    docs_dir = Path(args.docs_dir).expanduser().resolve() if args.docs_dir else default_docs
    reports_dir = (
        Path(args.reports_dir).expanduser().resolve() if args.reports_dir else default_reports
    )

    if not docs_dir.exists() or not docs_dir.is_dir():
        print(f"invalid docs_dir: {docs_dir}")
        return 2

    try:
        src_a, src_b = _resolve_sources(args, docs_dir)
        outputs = run_compare_pipeline(src_a, src_b, docs_dir, reports_dir)
    except Exception as exc:
        print(f"error: {exc}")
        return 1

    print("minimal report generated:")
    print(f"  html: {outputs['html']}")
    print(f"  md  : {outputs['md']}")
    print(f"  txt : {outputs['txt']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
