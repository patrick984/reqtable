#!/usr/bin/env python3

from __future__ import annotations

import shutil
import tempfile
import zipapp
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"


def main() -> None:
    DIST.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        staging = Path(directory)
        shutil.copytree(
            ROOT / "reqtable",
            staging / "reqtable",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        (staging / "__main__.py").write_text(
            "from reqtable.cli import main\nraise SystemExit(main())\n",
            encoding="utf-8",
        )
        zipapp.create_archive(
            staging,
            target=DIST / "reqtable.pyz",
            interpreter="/usr/bin/env python3",
            compressed=True,
        )


if __name__ == "__main__":
    main()
