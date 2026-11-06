from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CliTests(unittest.TestCase):
    def test_snapshot_and_diff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / "old.csv"; new = root / "new.csv"
            old.write_text("ID,Text\nR1,Old\n", encoding="utf-8")
            new.write_text("ID,Text\nR1,New\nR2,Added\n", encoding="utf-8")
            snapshot = root / "snapshot.html"; diff = root / "diff.html"
            commands = [
                [sys.executable, "-m", "reqtable", str(new), "--id-column", "ID", "-o", str(snapshot)],
                [sys.executable, "-m", "reqtable", "--old", str(old), "--new", str(new), "--id-column", "ID", "-o", str(diff)],
            ]
            for command in commands:
                completed = subprocess.run(command, capture_output=True, text=True)
                self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("reqtable-data", snapshot.read_text(encoding="utf-8"))
            self.assertIn('"mode":"diff"', diff.read_text(encoding="utf-8"))

    def test_validation_exit_code(self) -> None:
        completed = subprocess.run([sys.executable, "-m", "reqtable"], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 2)

    def test_develop_mode_cli(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "requirements.csv"
            output = root / "develop.html"
            source.write_text("ID,Text\nR1,Hello\n", encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, "-m", "reqtable", str(source), "--id-column", "ID", "--document-mode", "develop", "-o", str(output)],
                capture_output=True, text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn('"documentMode":"develop"', output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
