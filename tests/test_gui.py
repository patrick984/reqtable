from __future__ import annotations

import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from reqtable import cli
from reqtable.gui import (
    WORKFLOWS, BadRequest, GuiError, build_argv, launcher, posix_command, powershell_command, script, workflow_named,
)
from test_xlsx_import import write_workbook

REPORT = {"input": "reqs.csv", "output": "reqs.html", "id_column": "ID"}


def run_cli(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    here = Path(cli.__file__).resolve().parent.parent
    return subprocess.run(
        [sys.executable, "-m", "reqtable", *argv], cwd=cwd, capture_output=True, text=True, env={"PYTHONPATH": str(here)},
    )


class BuildArgvTests(unittest.TestCase):
    def test_report_puts_positional_first_and_skips_empty_values(self) -> None:
        argv = build_argv(workflow_named("report"), {"output": "out.html", "id_column": "ID", "title": "", "input": "reqs.csv"})
        self.assertEqual(argv, ["reqs.csv", "-o", "out.html", "--id-column", "ID"])

    def test_report_develop_mode_and_advanced_values(self) -> None:
        argv = build_argv(workflow_named("report"), {**REPORT, "document_mode": "develop", "title": "My reqs", "encoding": "latin-1"})
        self.assertEqual(
            argv, ["reqs.csv", "-o", "reqs.html", "--id-column", "ID", "--document-mode", "develop", "--title", "My reqs", "--encoding", "latin-1"]
        )

    def test_diff(self) -> None:
        argv = build_argv(workflow_named("diff"), {
            "old": "a.csv", "new": "b.csv", "output": "d.html", "id_column": "ID",
            "initial_diff_view": "side-by-side", "changes_only": "on", "include_unchanged": "off",
        })
        self.assertEqual(argv, [
            "--old", "a.csv", "--new", "b.csv", "-o", "d.html", "--id-column", "ID",
            "--initial-diff-view", "side-by-side", "--changes-only", "--no-include-unchanged",
        ])

    def test_comments(self) -> None:
        argv = build_argv(workflow_named("comments"), {"report": "r.html", "output": "c.csv", "csv_base": "union", "allow_comment_loss": "on"})
        self.assertEqual(argv, ["--extract-comments", "r.html", "-o", "c.csv", "--csv-base", "union", "--allow-comment-loss"])

    def test_list_tables(self) -> None:
        self.assertEqual(build_argv(workflow_named("list_tables"), {"workbook": "w.xlsx"}), ["--list-tables", "w.xlsx"])

    def test_to_csv_uses_excel_fields_only_for_a_workbook(self) -> None:
        values = {"input": "w.xlsx", "output": "o.csv", "id_column": "ID", "sheet": "Reqs", "header_row": "3"}
        self.assertEqual(
            build_argv(workflow_named("to_csv"), values),
            ["w.xlsx", "-o", "o.csv", "--id-column", "ID", "--sheet", "Reqs", "--header-row", "3"],
        )

    def test_excel_fields_are_dropped_when_the_input_is_a_csv(self) -> None:
        argv = build_argv(workflow_named("report"), {**REPORT, "table": "Requirements", "header_row": "2"})
        self.assertEqual(argv, ["reqs.csv", "-o", "reqs.html", "--id-column", "ID"])

    def test_paths_inside_the_working_folder_are_relative(self) -> None:
        argv = build_argv(
            workflow_named("report"),
            {"input": "/work/data/reqs.csv", "output": "/elsewhere/out.html", "id_column": "ID"},
            workdir=Path("/work"),
        )
        self.assertEqual(argv[:3], ["data/reqs.csv", "-o", "/elsewhere/out.html"])

    def test_missing_required_fields_are_named_by_label(self) -> None:
        with self.assertRaises(GuiError) as caught:
            build_argv(workflow_named("diff"), {"old": "a.csv"})
        message = str(caught.exception)
        self.assertIn("Newer version", message)
        self.assertIn("Save the report as", message)
        self.assertNotIn("Older version", message)

    def test_unknown_names_and_values_are_bad_requests(self) -> None:
        with self.assertRaises(BadRequest):
            workflow_named("nope")
        with self.assertRaises(BadRequest):
            build_argv(workflow_named("report"), {**REPORT, "bogus": "x"})
        with self.assertRaises(BadRequest):
            build_argv(workflow_named("report"), {**REPORT, "document_mode": "publish"})

    def test_a_value_that_looks_like_a_flag_cannot_become_one(self) -> None:
        with self.assertRaises(GuiError):
            build_argv(workflow_named("report"), {**REPORT, "input": "-o"})
        argv = build_argv(workflow_named("report"), {**REPORT, "title": "-draft"})
        self.assertIn("--title=-draft", argv)


TRICKY = ["it's", 'say "hi"', "$HOME `x` $(y)", "two  spaces", "back\\slash", "semi;colon", "", "ünï", "*.csv"]


class QuotingTests(unittest.TestCase):
    def test_posix_command_round_trips_through_shlex(self) -> None:
        argv = ["req file.csv", "--title", *TRICKY, "-o", "out dir/x.html"]
        for program in (("reqtable.pyz",), ("/tmp/my dir/reqtable.pyz",), ("-m", "reqtable")):
            with self.subTest(program=program):
                self.assertEqual(shlex.split(posix_command(argv, program).replace("\\\n", "")), ["python3", *program, *argv])

    def test_long_posix_command_wraps_one_flag_group_per_line_and_still_round_trips(self) -> None:
        argv = ["requirements.csv", "--id-column", "ID", "--document-mode", "develop", "--title", "A long report title", "-o", "requirements-develop.html"]
        text = posix_command(argv)
        lines = text.split("\n")
        self.assertEqual(lines[0], "python3 reqtable.pyz requirements.csv \\")
        self.assertEqual(lines[1], "  --id-column ID \\")
        self.assertEqual(lines[-1], "  -o requirements-develop.html")
        self.assertEqual(shlex.split(text.replace("\\\n", "")), ["python3", "reqtable.pyz", *argv])

    def test_short_command_stays_on_one_line(self) -> None:
        self.assertEqual(posix_command(["a.csv", "-o", "a.html"]), "python3 reqtable.pyz a.csv -o a.html")
        self.assertEqual(powershell_command(["a.csv", "-o", "a.html"]), "python reqtable.pyz a.csv -o a.html")

    def test_powershell_single_quotes_double_embedded_quotes(self) -> None:
        text = powershell_command(["--title", "it's $HOME", "C:\\My Docs\\a.csv", "x;y"])
        self.assertEqual(text, "python reqtable.pyz --title 'it''s $HOME' 'C:\\My Docs\\a.csv' 'x;y'")

    def test_powershell_quotes_empty_and_comma_and_splat_tokens(self) -> None:
        self.assertEqual(powershell_command(["", "a,b", "@x"]), "python reqtable.pyz '' 'a,b' '@x'")

    def test_powershell_wraps_with_backticks(self) -> None:
        argv = ["requirements.csv", "--id-column", "ID", "--document-mode", "develop", "--title", "A long report title", "-o", "requirements-develop.html"]
        lines = powershell_command(argv).split("\n")
        self.assertTrue(all(line.endswith(" `") for line in lines[:-1]))
        self.assertEqual(lines[-1], "  -o requirements-develop.html")


class ScriptTests(unittest.TestCase):
    STEPS = [("Make a report from a spreadsheet", ["a.csv", "-o", "a.html"]), ("Compare two versions", ["--old", "o.csv", "--new", "n.csv", "-o", "d.html"])]

    def test_sh_script(self) -> None:
        text = script(self.STEPS, "sh", Path("/my work"))
        self.assertEqual(text.splitlines()[:3], ["#!/bin/sh", "set -e", "cd '/my work'"])
        self.assertIn("# Compare two versions\npython3 reqtable.pyz --old o.csv --new n.csv -o d.html", text)
        self.assertNotIn("LASTEXITCODE", text)

    def test_powershell_script_checks_the_exit_code_after_each_step(self) -> None:
        text = script(self.STEPS, "powershell", Path("C:\\My Work"))
        self.assertEqual(text.splitlines()[:2], ["$ErrorActionPreference = 'Stop'", "Set-Location -LiteralPath 'C:\\My Work'"])
        self.assertEqual(text.count("if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"), 2)
        self.assertIn("python reqtable.pyz a.csv -o a.html\nif ($LASTEXITCODE", text)

    def test_empty_script_is_still_valid(self) -> None:
        self.assertEqual(script([], "sh", Path("/w")), "#!/bin/sh\nset -e\ncd /w\n")


class LauncherTests(unittest.TestCase):
    def test_source_checkout_runs_the_module(self) -> None:
        found = launcher(Path("/work"))
        self.assertEqual(found.shown, ("-m", "reqtable"))
        self.assertEqual(found.run, (sys.executable, "-m", "reqtable"))
        self.assertTrue((Path(found.env["PYTHONPATH"]) / "reqtable").is_dir())

    def test_zipapp_shows_the_archive_relative_to_the_working_folder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            archive = root / "tools" / "reqtable.pyz"
            archive.parent.mkdir()
            archive.write_bytes(b"")
            found = launcher(root, str(archive / "reqtable" / "gui.py"))
            self.assertEqual(found.shown, ("tools/reqtable.pyz",))
            self.assertEqual(found.run, (sys.executable, str(archive)))
            self.assertEqual(launcher(root / "other", str(archive / "reqtable" / "gui.py")).shown, (str(archive),))


class RegistryMatchesParserTests(unittest.TestCase):
    def test_every_flag_and_choice_is_accepted_by_the_cli_parser(self) -> None:
        actions = {option: action for action in cli.parser()._actions for option in action.option_strings}
        positionals = [action.dest for action in cli.parser()._actions if not action.option_strings and action.dest != "help"]
        self.assertEqual(positionals, ["input"])
        for workflow in WORKFLOWS:
            positional = [f.name for f in workflow.fields if f.flag is None]
            self.assertLessEqual(positional, ["input"], workflow.id)
            names = [f.name for f in workflow.fields]
            self.assertEqual(len(names), len(set(names)), workflow.id)
            for field in workflow.fields:
                where = f"{workflow.id}.{field.name}"
                if field.flag is None:
                    continue
                self.assertIn(field.flag, actions, where)
                action = actions[field.flag]
                values = [value for value, _ in field.choices if value]
                if field.kind == "flag":
                    self.assertTrue(set(values) <= {"on", "off"}, where)
                    if "off" in values:
                        self.assertIn("--no-" + field.flag[2:], actions, where)
                    self.assertEqual(action.nargs, 0, where)
                else:
                    self.assertNotEqual(action.nargs, 0, where)
                    for value in values:
                        self.assertIn(value, action.choices or (), f"{where}={value}")
                    if action.choices is not None:
                        self.assertEqual(field.kind, "choice", where)
                if field.kind == "choice":
                    self.assertTrue(field.choices, where)
                    self.assertIn(field.default or values[0], values, where)

    def test_every_field_has_plain_language_text(self) -> None:
        for workflow in WORKFLOWS:
            self.assertTrue(workflow.when.startswith("Use this "), workflow.id)
            for field in workflow.fields:
                self.assertTrue(field.label and field.help.endswith("."), f"{workflow.id}.{field.name}")


class CommandsRunTests(unittest.TestCase):
    def test_every_workflow_builds_a_command_the_cli_accepts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "reqs.csv").write_text("ID,Text\nR1,Hello\nR2,World\n", encoding="utf-8")
            (root / "reqs2.csv").write_text("ID,Text\nR1,Hello again\n", encoding="utf-8")
            write_workbook(root / "book.xlsx")
            cases = {
                "report": {"input": "reqs.csv", "output": "r.html", "id_column": "ID", "document_mode": "develop"},
                "diff": {"old": "reqs.csv", "new": "reqs2.csv", "output": "d.html", "id_column": "ID", "initial_diff_view": "side-by-side", "include_unchanged": "on"},
                "to_csv": {"input": str(root / "book.xlsx"), "output": "book.csv", "id_column": "Req ID", "sheet": "Reqs"},
                "list_tables": {"workbook": "book.xlsx"},
            }
            for workflow_id, values in cases.items():
                with self.subTest(workflow_id):
                    completed = run_cli(build_argv(workflow_named(workflow_id), values, root), root)
                    self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue((root / "r.html").is_file())
            self.assertTrue((root / "book.csv").is_file())
            extracted = run_cli(
                build_argv(workflow_named("comments"), {"report": "r.html", "output": "c.csv", "comments_format": "text"}, root), root
            )
            self.assertEqual(extracted.returncode, 0, extracted.stderr)
            self.assertTrue((root / "c.csv").is_file())


if __name__ == "__main__":
    unittest.main()
