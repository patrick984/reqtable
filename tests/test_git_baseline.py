from __future__ import annotations

import contextlib
import io
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from reqtable.cli import main


def report_data(path: Path) -> dict:
    match = re.search(
        r'<script[^>]*id="reqtable-data"[^>]*>(.*?)</script>',
        path.read_text(encoding="utf-8"),
        re.S,
    )
    return json.loads(match.group(1))


@unittest.skipUnless(shutil.which("git"), "git is not on PATH")
class GitBaselineTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.csv = self.root / "requirements.csv"
        self.csv.write_text("ID,Text\nR1,One\nR2,Two\n", encoding="utf-8")
        self.git("init", "-q")
        self.git("add", "requirements.csv")
        self.git(
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.com",
            "commit",
            "-q",
            "-m",
            "first",
        )
        self.csv.write_text("ID,Text\nR1,One changed\nR3,Three\n", encoding="utf-8")
        self.git("add", "requirements.csv")
        self.git(
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.com",
            "commit",
            "-q",
            "-m",
            "second",
        )
        self.csv.write_text(
            "ID,Text\nR1,One changed again\nR3,Three\n", encoding="utf-8"
        )
        self.output = self.root / "out.html"

    def git(self, *args: str) -> None:
        subprocess.run(
            ["git", "-C", str(self.root), *args], check=True, capture_output=True
        )

    def run_main(self, *args: str) -> tuple[int, str]:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = main([*args, "--id-column", "ID", "-o", str(self.output)])
        return code, stderr.getvalue()

    def statuses(self) -> dict[str, str]:
        return report_data(self.output)["diffStatus"]

    def test_old_head_compares_against_committed_file(self) -> None:
        code, err = self.run_main("--old", "git:HEAD", "--new", str(self.csv))
        self.assertEqual(code, 0, err)
        self.assertEqual(self.statuses(), {"R1": "changed", "R3": "unchanged"})
        self.assertRegex(
            report_data(self.output)["meta"]["oldFilename"],
            r"^requirements\.csv @ HEAD \([0-9a-f]+\)$",
        )

    def test_explicit_path_and_older_rev(self) -> None:
        code, err = self.run_main(
            "--old", f"git:HEAD~1:{self.csv}", "--new", str(self.csv)
        )
        self.assertEqual(code, 0, err)
        self.assertEqual(
            self.statuses(), {"R1": "changed", "R2": "removed", "R3": "added"}
        )
        self.assertIn("@ HEAD~1 (", report_data(self.output)["meta"]["oldFilename"])

    def test_develop_mode(self) -> None:
        code, err = self.run_main(
            "--old", "git:HEAD", "--new", str(self.csv), "--document-mode", "develop"
        )
        self.assertEqual(code, 0, err)
        self.assertEqual(report_data(self.output)["meta"]["documentMode"], "develop")

    def test_unknown_rev_fails_cleanly(self) -> None:
        code, err = self.run_main("--old", "git:no-such-rev", "--new", str(self.csv))
        self.assertEqual(code, 3)
        self.assertIn("no-such-rev", err)
        self.assertFalse(self.output.exists())

    def test_path_absent_at_rev_fails_cleanly(self) -> None:
        other = self.root / "other.csv"
        other.write_text("ID,Text\nR1,x\n", encoding="utf-8")
        code, err = self.run_main("--old", "git:HEAD", "--new", str(other))
        self.assertEqual(code, 3)
        self.assertIn("other.csv", err)

    def test_not_a_repository(self) -> None:
        with tempfile.TemporaryDirectory() as outside:
            lone = Path(outside) / "x.csv"
            lone.write_text("ID,Text\nR1,x\n", encoding="utf-8")
            code, err = self.run_main("--old", "git:HEAD", "--new", str(lone))
        self.assertEqual(code, 3)
        self.assertIn("error:", err)

    def test_plain_file_old_still_works(self) -> None:
        old = self.root / "old.csv"
        old.write_text("ID,Text\nR1,Old\n", encoding="utf-8")
        code, err = self.run_main("--old", str(old), "--new", str(self.csv))
        self.assertEqual(code, 0, err)
        self.assertEqual(report_data(self.output)["meta"]["oldFilename"], "old.csv")
        self.assertEqual(self.statuses()["R3"], "added")


if __name__ == "__main__":
    unittest.main()
