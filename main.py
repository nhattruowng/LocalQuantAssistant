"""CLI entrypoint for LocalQuant Assistant."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from app.cli import run_cli


if __name__ == "__main__":
    run_cli()
