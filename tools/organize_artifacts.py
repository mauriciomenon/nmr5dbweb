from __future__ import annotations

import shutil
from pathlib import Path


def main() -> None:
    """Move runtime artifact files from the repo root into artifacts/.

    This script is safe to run multiple times. It only considers files that
    live directly in the project root (same folder as main.py / README.md).
    """

    project_root = Path(__file__).resolve().parent.parent
    artifacts_dir = project_root / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)

    # Patterns of files that are clearly runtime artifacts or benchmark outputs
    patterns = [
        "*.duckdb",               # DuckDB databases generated during use/benchmarks
        "benchmark_results_*.json",
        "benchmark_run*.log",
    ]

    candidates: list[Path] = []
    for pattern in patterns:
        for path in project_root.glob(pattern):
            # Skip anything that is already inside artifacts/ (defensive)
            if artifacts_dir in path.parents:
                continue
            candidates.append(path)

    if not candidates:
        print("No artifact files found in project root.")
        return

    print("The following files will be moved to artifacts/:")
    for path in candidates:
        print(f"  - {path.name}")

    answer = input("Proceed? [y/N]: ").strip().lower()
    if answer not in {"y", "yes"}:
        print("Aborted. No files were moved.")
        return

    for src in candidates:
        dest = artifacts_dir / src.name
        print(f"Moving {src.name} -> artifacts/{src.name}")
        shutil.move(str(src), str(dest))

    print("Done. Artifacts are now under artifacts/.")


if __name__ == "__main__":  # pragma: no cover
    main()
