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

CSV_TEXT = (
    "ID,Type,Name,Part of,Allocated to,Verified by,Compliance\n"
    "SYS-A,System,Product,,,,\n"
    "SYS-B,System,Other,,,,\n"
    "R1,,One,,SYS-A,,Not verified\n"
    "R2,,Two,,SYS-B,,Not verified\n"
)
BASE = ("--id-column", "ID", "--traceability")
CONTRACT_KEYS = {
    "name", "gate", "gateName", "produces", "system", "created", "createdBy", "hash", "hashOk", "includes",
    "capturesStatus", "statusColumns", "source", "headers", "rows", "signoffs", "approval",
}


def report_data(path: Path) -> dict:
    match = re.search(r'<script[^>]*id="reqtable-data"[^>]*>(.*?)</script>', path.read_text(encoding="utf-8"), re.S)
    return json.loads(match.group(1))


class CliTestCase(unittest.TestCase):
    store = "files"

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.csv = self.root / "requirements.csv"
        self.csv.write_text(CSV_TEXT, encoding="utf-8")
        self.output = self.root / "out.html"
        self.config = self.write_config({})

    def write_config(self, content: dict) -> str:
        path = self.root / "config.json"
        path.write_text(json.dumps({**content, "baselines": {"store": self.store}}), encoding="utf-8")
        return str(path)

    def run_main(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main([*args, *BASE, "-c", self.config])
        return code, out.getvalue(), err.getvalue()

    def embed(self, names: str, source: Path | None = None) -> tuple[int, dict | None, str]:
        code, _, err = self.run_main(str(source or self.csv), "--baselines", names, "-o", str(self.output))
        return code, report_data(self.output) if code == 0 else None, err


class FileStoreCliTests(CliTestCase):
    def test_create_list_and_renumber(self) -> None:
        self.assertEqual(self.run_main(str(self.csv), "--list-baselines")[1], "No baselines.\n")
        code, out, _ = self.run_main(str(self.csv), "--create-baseline", "SRR")
        self.assertEqual(code, 0)
        self.assertRegex(out, rf"^Created baseline SRR \(sha256:[0-9a-f]{{64}}\) in {re.escape(str(self.root))}.*SRR\n$")
        self.run_main(str(self.csv), "--create-baseline", "SRR")
        self.run_main(str(self.csv), "--create-baseline", "DDR", "--system", "SYS-A")
        code, out, _ = self.run_main("--new", str(self.csv), "--list-baselines")
        lines = [line.split("\t") for line in out.splitlines()]
        self.assertEqual([(l[0], l[1], l[2]) for l in lines], [("SRR", "SRR", "-"), ("SRR-2", "SRR", "-"), ("DDR/SYS-A", "DDR", "SYS-A")])
        self.assertTrue(all(len(l) == 6 and re.fullmatch(r"[0-9a-f]{12}", l[5]) for l in lines))

    def test_embed_follows_the_contract_and_scopes_rows(self) -> None:
        self.run_main(str(self.csv), "--create-baseline", "SRR")
        self.run_main(str(self.csv), "--create-baseline", "DDR", "--system", "SYS-A")
        self.csv.write_text(CSV_TEXT.replace("One", "Uno"), encoding="utf-8")
        code, data, err = self.embed("SRR,DDR/SYS-A")
        self.assertEqual((code, err), (0, ""))
        srr, ddr = data["baselines"]
        self.assertEqual(set(srr), CONTRACT_KEYS)
        self.assertEqual((srr["name"], srr["gate"], srr["system"], srr["hashOk"]), ("SRR", "SRR", None, True))
        self.assertEqual(srr["gateName"], "System Requirements Review")
        self.assertEqual(srr["headers"][0], "ID")
        self.assertEqual([row["ID"] for row in srr["rows"]], ["SYS-A", "SYS-B", "R1", "R2"])
        self.assertEqual(srr["rows"][2]["Name"], "One")
        self.assertEqual([row["ID"] for row in ddr["rows"]], ["SYS-A", "R1"])
        self.assertEqual((ddr["system"], ddr["hashOk"], ddr["includes"]), ("SYS-A", True, ["Requirement", "System"]))
        self.assertTrue(ddr["hash"].startswith("sha256:"))

    def test_no_baselines_key_content_without_the_flag(self) -> None:
        self.assertEqual(self.run_main(str(self.csv), "-o", str(self.output))[0], 0)
        self.assertEqual(report_data(self.output)["baselines"], [])

    def test_embeds_in_diff_mode(self) -> None:
        self.run_main(str(self.csv), "--create-baseline", "SRR")
        code, _, _ = self.run_main("--old", str(self.csv), "--new", str(self.csv), "--baselines", "SRR", "-o", str(self.output))
        self.assertEqual(code, 0)
        self.assertEqual(report_data(self.output)["baselines"][0]["name"], "SRR")

    def test_removed_gate_falls_back_to_its_id(self) -> None:
        self.run_main(str(self.csv), "--create-baseline", "SRR")
        self.config = self.write_config({"gates": [{"id": "PDR"}]})
        code, _, _ = self.run_main(str(self.csv), "--baselines", "SRR", "-o", str(self.output))
        self.assertEqual(code, 0)
        entry = report_data(self.output)["baselines"][0]
        self.assertEqual((entry["gateName"], entry["produces"]), ("SRR", ""))

    def test_tampered_baseline_warns_and_is_flagged(self) -> None:
        self.run_main(str(self.csv), "--create-baseline", "SRR")
        frozen = self.root / "baselines" / "SRR" / "requirements.csv"
        frozen.write_bytes(frozen.read_bytes().replace(b"One", b"Won"))
        code, data, err = self.embed("SRR")
        self.assertEqual(code, 0)
        self.assertIn("warning: baseline SRR does not match its recorded hash", err)
        self.assertFalse(data["baselines"][0]["hashOk"])

    def test_unknown_name_lists_existing_names(self) -> None:
        self.run_main(str(self.csv), "--create-baseline", "SRR")
        code, _, err = self.embed("PDR")
        self.assertEqual(code, 3)
        self.assertIn("unknown baseline 'PDR'", err)
        self.assertIn("existing baselines: SRR", err)

    def test_system_argument_errors(self) -> None:
        for args, code in (
            (("--create-baseline", "DDR"), 2),
            (("--create-baseline", "SRR", "--system", "SYS-A"), 2),
            (("--create-baseline", "DDR", "--system", "R1"), 3),
            (("--create-baseline", "DDR", "--system", "NOPE"), 3),
            (("--create-baseline", "NOPE"), 2),
            (("--list-baselines", "--system", "SYS-A"), 2),
            (("--system", "SYS-A", "-o", str(self.output)), 2),
        ):
            with self.subTest(args):
                self.assertEqual(self.run_main(str(self.csv), *args)[0], code)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = main([str(self.csv), "-c", self.config, "--id-column", "ID", "--create-baseline", "DDR", "--system", "SYS-A"])
        self.assertEqual(code, 2)
        self.assertIn("--traceability", err.getvalue())
        self.assertFalse((self.root / "baselines").exists())

    def test_cannot_combine_with_diff_options(self) -> None:
        for args in (
            ("--create-baseline", "SRR", "--old", str(self.csv)),
            ("--create-baseline", "SRR", "--new", str(self.csv)),
            ("--list-baselines", "--old", str(self.csv)),
            ("--list-baselines", "--extract-comments", "x.html"),
            ("--list-baselines", "--create-baseline", "SRR"),
            ("--create-baseline", "SRR", "--baselines", "SRR"),
        ):
            with self.subTest(args):
                self.assertEqual(self.run_main(str(self.csv), *args)[0], 2)
        self.assertEqual(self.run_main("--create-baseline", "SRR")[0], 2)


@unittest.skipUnless(shutil.which("git"), "git is not on PATH")
class GitStoreCliTests(CliTestCase):
    store = "git"

    def setUp(self) -> None:
        super().setUp()
        self.git("init", "-q")
        self.git("config", "user.name", "Tester")
        self.git("config", "user.email", "t@example.com")
        self.git("add", "requirements.csv")
        self.git("commit", "-q", "-m", "first")

    def git(self, *args: str) -> str:
        return subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True, text=True).stdout

    def test_create_list_and_embed(self) -> None:
        code, out, _ = self.run_main(str(self.csv), "--create-baseline", "SRR")
        self.assertEqual(code, 0)
        self.assertRegex(out, r"^Created baseline SRR \(sha256:[0-9a-f]{64}\) as tag baseline/SRR\n$")
        self.run_main(str(self.csv), "--create-baseline", "DDR", "--system", "SYS-A")
        self.assertEqual(self.git("tag", "-l").split(), ["baseline/DDR/SYS-A", "baseline/SRR"])
        _, out, _ = self.run_main(str(self.csv), "--list-baselines")
        lines = [line.split("\t") for line in out.splitlines()]
        self.assertEqual([(l[0], l[2], l[4]) for l in lines], [("SRR", "-", "Tester"), ("DDR/SYS-A", "SYS-A", "Tester")])
        self.csv.write_text(CSV_TEXT.replace("One", "Uno"), encoding="utf-8")
        self.git("commit", "-q", "-am", "edit")
        code, _, err = self.run_main(str(self.csv), "--baselines", "SRR,DDR/SYS-A", "-o", str(self.output))
        self.assertEqual((code, err), (0, ""))
        srr, ddr = report_data(self.output)["baselines"]
        self.assertEqual(srr["rows"][2]["Name"], "One")
        self.assertEqual([row["ID"] for row in ddr["rows"]], ["SYS-A", "R1"])
        self.assertTrue(srr["hashOk"] and ddr["hashOk"])
        self.assertEqual(srr["source"], "requirements.csv")

    def test_dirty_input_is_refused(self) -> None:
        self.csv.write_text(CSV_TEXT + "R3,,Three,,SYS-A,,\n", encoding="utf-8")
        code, _, err = self.run_main(str(self.csv), "--create-baseline", "SRR")
        self.assertEqual(code, 3)
        self.assertIn("uncommitted", err)


if __name__ == "__main__":
    unittest.main()
