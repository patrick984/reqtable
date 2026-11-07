from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from reqtable.cli import main as reqtable  # noqa: E402

UAT = ["requirements-uat.csv", "--id-column", "ID", "--traceability"]
REPORTS = {
    "requirements-uat-develop.html": [*UAT, "--document-mode", "develop"],
    "requirements-uat.html": UAT,
    "examples/requirements-diff.html": [
        "--old", "examples/requirements-old.csv", "--new", "examples/requirements-new.csv",
        "-c", "examples/config.json",
    ],
}


def main() -> int:
    for output, args in REPORTS.items():
        code = reqtable([*(str(ROOT / arg) if arg.endswith((".csv", ".json")) else arg for arg in args),
                         "-o", str(ROOT / output)])
        if code:
            print(f"failed: {output}", file=sys.stderr)
            return code
        print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
