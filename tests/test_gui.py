from __future__ import annotations

import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from reqtable import cli
from reqtable.gui import (
    GROUPS,
    WORKFLOWS,
    BadRequest,
    ScriptStep,
    GuiError,
    blocked_checks,
    build_argv,
    guess_id_column,
    launcher,
    lookup_source,
    posix_command,
    powershell_command,
    quote_windows,
    script,
    workflow_named,
)
from reqtable.signoff import DECISIONS
from test_xlsx_import import write_workbook

REPORT = {"input": "reqs.csv", "output": "reqs.html", "id_column": "ID"}


def run_cli(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    here = Path(cli.__file__).resolve().parent.parent
    return subprocess.run(
        [sys.executable, "-m", "reqtable", *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(here)},
    )


class BuildArgvTests(unittest.TestCase):
    def test_report_puts_positional_first_and_skips_empty_values(self) -> None:
        argv = build_argv(
            workflow_named("report"),
            {"output": "out.html", "id_column": "ID", "title": "", "input": "reqs.csv"},
        )
        self.assertEqual(argv, ["reqs.csv", "--id-column", "ID", "-o", "out.html"])

    def test_report_develop_mode_and_advanced_values(self) -> None:
        argv = build_argv(
            workflow_named("report"),
            {
                **REPORT,
                "document_mode": "develop",
                "title": "My reqs",
                "encoding": "latin-1",
            },
        )
        self.assertEqual(
            argv,
            [
                "reqs.csv",
                "--id-column",
                "ID",
                "-o",
                "reqs.html",
                "--document-mode",
                "develop",
                "--title",
                "My reqs",
                "--encoding",
                "latin-1",
            ],
        )

    def test_develop_card_always_emits_develop_mode_and_has_no_mode_field(self) -> None:
        develop = workflow_named("develop")
        self.assertNotIn("document_mode", [f.name for f in develop.fields])
        self.assertEqual(
            build_argv(develop, REPORT),
            [
                "reqs.csv",
                "--id-column",
                "ID",
                "-o",
                "reqs.html",
                "--document-mode",
                "develop",
            ],
        )
        with self.assertRaises(BadRequest):
            build_argv(develop, {**REPORT, "document_mode": "review"})

    def test_a_header_row_without_a_sheet_is_dropped(self) -> None:
        values = {**REPORT, "input": "w.xlsx", "table": "Reqs", "header_row": "3"}
        self.assertNotIn("--header-row", build_argv(workflow_named("report"), values))
        self.assertIn(
            "--header-row",
            build_argv(
                workflow_named("report"), {**values, "table": "", "sheet": "Reqs"}
            ),
        )

    def test_excel_choices_come_before_the_id_column_and_the_output(self) -> None:
        for workflow_id in ("report", "diff", "to_csv"):
            names = [f.name for f in workflow_named(workflow_id).fields]
            order = [
                names.index(n)
                for n in ("table", "sheet", "header_row", "id_column", "output")
            ]
            self.assertEqual(order, sorted(order), workflow_id)
            self.assertLess(names.index("id_column"), names.index("output"))

    def test_diff_takes_a_document_mode(self) -> None:
        argv = build_argv(
            workflow_named("diff"),
            {
                "old": "a.csv",
                "new": "b.csv",
                "output": "d.html",
                "document_mode": "develop",
            },
        )
        self.assertEqual(
            argv,
            [
                "--old",
                "a.csv",
                "--new",
                "b.csv",
                "-o",
                "d.html",
                "--document-mode",
                "develop",
            ],
        )

    def test_diff(self) -> None:
        argv = build_argv(
            workflow_named("diff"),
            {
                "old": "a.csv",
                "new": "b.csv",
                "output": "d.html",
                "id_column": "ID",
                "initial_diff_view": "side-by-side",
                "changes_only": "on",
                "include_unchanged": "off",
            },
        )
        self.assertEqual(
            argv,
            [
                "--old",
                "a.csv",
                "--new",
                "b.csv",
                "--id-column",
                "ID",
                "-o",
                "d.html",
                "--initial-diff-view",
                "side-by-side",
                "--changes-only",
                "--no-include-unchanged",
            ],
        )

    def test_comments(self) -> None:
        argv = build_argv(
            workflow_named("comments"),
            {
                "report": "r.html",
                "output": "c.csv",
                "csv_base": "union",
                "allow_comment_loss": "on",
            },
        )
        self.assertEqual(
            argv,
            [
                "--extract-comments",
                "r.html",
                "-o",
                "c.csv",
                "--csv-base",
                "union",
                "--allow-comment-loss",
            ],
        )

    def test_list_tables(self) -> None:
        self.assertEqual(
            build_argv(workflow_named("list_tables"), {"workbook": "w.xlsx"}),
            ["--list-tables", "w.xlsx"],
        )

    def test_to_csv_uses_excel_fields_only_for_a_workbook(self) -> None:
        values = {
            "input": "w.xlsx",
            "output": "o.csv",
            "id_column": "ID",
            "sheet": "Reqs",
            "header_row": "3",
        }
        self.assertEqual(
            build_argv(workflow_named("to_csv"), values),
            [
                "w.xlsx",
                "--sheet",
                "Reqs",
                "--header-row",
                "3",
                "--id-column",
                "ID",
                "-o",
                "o.csv",
            ],
        )

    def test_excel_fields_are_dropped_when_the_input_is_a_csv(self) -> None:
        argv = build_argv(
            workflow_named("report"),
            {**REPORT, "table": "Requirements", "header_row": "2"},
        )
        self.assertEqual(argv, ["reqs.csv", "--id-column", "ID", "-o", "reqs.html"])

    def test_an_excel_evidence_file_does_not_make_the_input_a_workbook(self) -> None:
        argv = build_argv(
            workflow_named("sign_off"),
            {
                "input": "reqs.csv",
                "baseline": "srr-1",
                "role": "Chief engineer",
                "decision": DECISIONS[0],
                "evidence": "approval.xlsx",
                "table": "Stray",
                "sheet": "Old",
                "header_row": "3",
            },
        )
        self.assertNotIn("--table", argv)
        self.assertNotIn("--sheet", argv)
        self.assertIn("approval.xlsx", argv)

    def test_paths_inside_the_working_folder_are_relative(self) -> None:
        argv = build_argv(
            workflow_named("report"),
            {
                "input": "/work/data/reqs.csv",
                "output": "/elsewhere/out.html",
                "id_column": "ID",
            },
            workdir=Path("/work"),
        )
        self.assertEqual(
            [argv[0], *argv[-2:]], ["data/reqs.csv", "-o", "/elsewhere/out.html"]
        )

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


TRICKY = [
    "it's",
    'say "hi"',
    "$HOME `x` $(y)",
    "two  spaces",
    "back\\slash",
    "semi;colon",
    "",
    "ünï",
    "*.csv",
]


def _windows_argv(line: str) -> list[str]:
    """CommandLineToArgvW for the arguments after the program: 2n backslashes before a quote give n and the quote
    toggles quoting, 2n+1 give n and a literal quote, other backslashes are literal, and unquoted whitespace splits.
    A doubled quote inside quotes differs between the C runtimes, so reqtable must never emit one."""
    args: list[str] = []
    i, n = 0, len(line)
    while True:
        while i < n and line[i] in " \t":
            i += 1
        if i >= n:
            return args
        current, quoted = "", False
        while i < n and (quoted or line[i] not in " \t"):
            if line[i] == "\\":
                j = i
                while j < n and line[j] == "\\":
                    j += 1
                if j < n and line[j] == '"':
                    current += "\\" * ((j - i) // 2) + ('"' if (j - i) % 2 else "")
                    i = j + 1 if (j - i) % 2 else j
                else:
                    current += line[i:j]
                    i = j
            elif line[i] == '"':
                assert not (quoted and line[i + 1 : i + 2] == '"'), (
                    f"doubled quote inside quotes in {line!r}"
                )
                quoted = not quoted
                i += 1
            else:
                current += line[i]
                i += 1
        args.append(current)


def _powershell_tokens(text: str) -> list[str] | str:
    """The argument values PowerShell sees in one emitted command, or the verbatim tail after --%."""
    values: list[str] = []
    i = 0
    while i < len(text):
        if text[i] == " ":
            i += 1
        elif text[i] == "'":
            j, value = i + 1, ""
            while True:
                if text[j] == "'" and text[j + 1 : j + 2] == "'":
                    value, j = value + "'", j + 2
                elif text[j] == "'":
                    break
                else:
                    value, j = value + text[j], j + 1
            values.append(value)
            i = j + 1
        else:
            j = text.find(" ", i)
            j = len(text) if j < 0 else j
            if text[i:j] == "--%":
                return text[j + 1 :]
            values.append(text[i:j])
            i = j
    return values


def _windows_powershell_51(value: str) -> str:
    """Windows PowerShell 5.1 drops an empty value, and wraps a value in quotes when it has whitespace after an even
    number of quote characters, counting every quote, escaped or not, and without doubling trailing backslashes."""
    count = 0
    for char in value:
        if char == '"':
            count += 1
        elif char.isspace() and count % 2 == 0:
            return f'"{value}"'
    return value


def _powershell_7_legacy(value: str) -> str:
    """PowerShell 7 with $PSNativeCommandArgumentPassing = 'Legacy': the same wrap, except a quote right after a
    backslash is not counted, and trailing backslashes are doubled inside the added quotes."""
    count, after_backslash = 0, False
    for char in value:
        if char == '"' and not after_backslash:
            count += 1
        elif char.isspace() and count % 2 == 0:
            return '"' + value + "\\" * (len(value) - len(value.rstrip("\\"))) + '"'
        after_backslash = char == "\\"
    return value


def _powershell_7_standard(value: str) -> str:
    """PowerShell 7.3+ default for a program such as python.exe: quote the value the way the C runtime reads it."""
    return quote_windows(value)


class QuotingTests(unittest.TestCase):
    def test_powershell_command_reaches_python_unchanged_in_5_1_and_7(self) -> None:
        values = [
            'say "hi"',
            'say "hi" there',
            '5" pipe size',
            "C:\\My Docs\\",
            "C:\\My Docs\\a.csv",
            "back\\slash",
            "end\\",
            'a\\"b',
            'a\\\\" b',
            "it's $HOME",
            "$(Get-Date)",
            "two  spaces",
            "",
            "plain",
            "x;y",
            "@x",
            "a,b",
            "ünï",
        ]
        for value in values:
            argv = ["reqs.csv", "--title", value, "-o", "out dir/x.html"]
            for name, passing in (
                ("5.1", _windows_powershell_51),
                ("7 legacy", _powershell_7_legacy),
                ("7", _powershell_7_standard),
            ):
                with self.subTest(value=value, powershell=name):
                    text = powershell_command(argv)
                    self.assertTrue(text.startswith("python reqtable.pyz "), text)
                    tokens = _powershell_tokens(text.replace(" `\n", " "))
                    if isinstance(tokens, str):
                        line = tokens
                    else:
                        self.assertEqual(tokens[:2], ["python", "reqtable.pyz"])
                        line = " ".join(
                            passing(t) for t in tokens[2:] if t or name == "7"
                        )
                    self.assertEqual(_windows_argv(line), argv)

    def test_quote_windows_round_trips(self) -> None:
        for value in [*TRICKY, "a\\", "a b\\\\", '\\"', '"', "\t"]:
            self.assertEqual(_windows_argv(quote_windows(value)), [value], value)

    def test_posix_command_round_trips_through_shlex(self) -> None:
        argv = ["req file.csv", "--title", *TRICKY, "-o", "out dir/x.html"]
        for program in (
            ("reqtable.pyz",),
            ("/tmp/my dir/reqtable.pyz",),
            ("-m", "reqtable"),
        ):
            with self.subTest(program=program):
                self.assertEqual(
                    shlex.split(posix_command(argv, program).replace("\\\n", "")),
                    ["python3", *program, *argv],
                )

    def test_long_posix_command_wraps_one_flag_group_per_line_and_still_round_trips(
        self,
    ) -> None:
        argv = [
            "requirements.csv",
            "--id-column",
            "ID",
            "--document-mode",
            "develop",
            "--title",
            "A long report title",
            "-o",
            "requirements-develop.html",
        ]
        text = posix_command(argv)
        lines = text.split("\n")
        self.assertEqual(lines[0], "python3 reqtable.pyz requirements.csv \\")
        self.assertEqual(lines[1], "  --id-column ID \\")
        self.assertEqual(lines[-1], "  -o requirements-develop.html")
        self.assertEqual(
            shlex.split(text.replace("\\\n", "")), ["python3", "reqtable.pyz", *argv]
        )

    def test_short_command_stays_on_one_line(self) -> None:
        self.assertEqual(
            posix_command(["a.csv", "-o", "a.html"]),
            "python3 reqtable.pyz a.csv -o a.html",
        )
        self.assertEqual(
            powershell_command(["a.csv", "-o", "a.html"]),
            "python reqtable.pyz a.csv -o a.html",
        )

    def test_powershell_single_quotes_double_embedded_quotes(self) -> None:
        text = powershell_command(
            ["--title", "it's $HOME", "C:\\My Docs\\a.csv", "x;y"]
        )
        self.assertEqual(
            text, "python reqtable.pyz --title 'it''s $HOME' 'C:\\My Docs\\a.csv' 'x;y'"
        )

    def test_powershell_quotes_empty_and_comma_and_splat_tokens(self) -> None:
        self.assertEqual(
            powershell_command(["a,b", "@x"]), "python reqtable.pyz 'a,b' '@x'"
        )

    def test_powershell_wraps_with_backticks(self) -> None:
        argv = [
            "requirements.csv",
            "--id-column",
            "ID",
            "--document-mode",
            "develop",
            "--title",
            "A long report title",
            "-o",
            "requirements-develop.html",
        ]
        lines = powershell_command(argv).split("\n")
        self.assertTrue(all(line.endswith(" `") for line in lines[:-1]))
        self.assertEqual(lines[-1], "  -o requirements-develop.html")


class ScriptTests(unittest.TestCase):
    STEPS = [
        ScriptStep("Make a report from a spreadsheet", ["a.csv", "-o", "a.html"]),
        ScriptStep(
            "Compare two versions", ["--old", "o.csv", "--new", "n.csv", "-o", "d.html"]
        ),
    ]

    def test_sh_script(self) -> None:
        text = script(self.STEPS, "sh", Path("/my work"))
        self.assertEqual(
            text.splitlines()[:3], ["#!/bin/sh", "set -e", "cd '/my work'"]
        )
        self.assertIn(
            "# Compare two versions\npython3 reqtable.pyz --old o.csv --new n.csv -o d.html",
            text,
        )
        self.assertNotIn("LASTEXITCODE", text)

    def test_powershell_script_checks_the_exit_code_after_each_step(self) -> None:
        text = script(self.STEPS, "powershell", Path("C:\\My Work"))
        self.assertEqual(
            text.splitlines()[:2],
            [
                "$ErrorActionPreference = 'Stop'",
                "Set-Location -LiteralPath 'C:\\My Work'",
            ],
        )
        self.assertEqual(
            text.count("if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"), 2
        )
        self.assertIn("python reqtable.pyz a.csv -o a.html\nif ($LASTEXITCODE", text)

    def test_a_step_that_records_says_so_above_its_command_in_both_shells(self) -> None:
        steps = [
            *self.STEPS,
            ScriptStep(
                "Record a sign-off", ["r.csv", "--sign-off", "srr-1"], records=True
            ),
        ]
        for shell in ("sh", "powershell"):
            lines = script(steps, shell, Path("/w")).splitlines()  # type: ignore[arg-type]
            at = lines.index("# Record a sign-off")
            self.assertEqual(
                lines[at + 1],
                "# This step records a new entry each time the script runs.",
                shell,
            )
            self.assertEqual(
                sum("records a new entry" in line for line in lines), 1, shell
            )

    def test_every_workflow_whose_flag_writes_a_record_records(self) -> None:
        writes = {"--create-baseline", "--sign-off", "--import-decisions"}
        for workflow in WORKFLOWS:
            flags = {f.flag for f in workflow.fields} | set(workflow.fixed)
            self.assertEqual(workflow.records, bool(flags & writes), workflow.id)

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
            self.assertEqual(
                launcher(root / "other", str(archive / "reqtable" / "gui.py")).shown,
                (str(archive),),
            )


class RegistryMatchesParserTests(unittest.TestCase):
    def test_every_flag_and_choice_is_accepted_by_the_cli_parser(self) -> None:
        actions = {
            option: action
            for action in cli.parser()._actions
            for option in action.option_strings
        }
        positionals = [
            action.dest
            for action in cli.parser()._actions
            if not action.option_strings and action.dest != "help"
        ]
        self.assertEqual(positionals, ["input"])
        for workflow in WORKFLOWS:
            if workflow.panel != "form":
                continue
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
                elif field.kind == "waivers":
                    assert field.pair_flag is not None
                    self.assertIn(field.pair_flag, actions, where)
                    for flag in (field.flag, field.pair_flag):
                        self.assertEqual(
                            type(actions[flag]).__name__, "_AppendAction", where
                        )
                else:
                    self.assertNotEqual(action.nargs, 0, where)
                    if action.choices is None:
                        # The CLI matches decisions itself; test_sign_off_decisions_are_the_ones_the_cli_records covers them.
                        self.assertTrue(not values or field.name == "decision", where)
                    else:
                        self.assertIn(field.kind, ("choice", "radio"), where)
                        for value in values:
                            self.assertIn(value, action.choices, f"{where}={value}")
                if field.kind in ("choice", "radio"):
                    self.assertTrue(field.choices, where)
                    self.assertIn(field.default or values[0], values, where)
                else:
                    self.assertEqual(
                        field.choices if field.kind != "flag" else (), (), where
                    )

    def test_fixed_flags_are_real_and_never_also_a_field(self) -> None:
        actions = {
            option: action
            for action in cli.parser()._actions
            for option in action.option_strings
        }
        fixed = [w for w in WORKFLOWS if w.fixed]
        self.assertTrue(fixed)
        for workflow in fixed:
            flag, *rest = workflow.fixed
            self.assertIn(flag, actions, workflow.id)
            action = actions[flag]
            if rest:
                self.assertIn(rest[0], action.choices or (), workflow.id)
            else:
                self.assertEqual(action.nargs, 0, workflow.id)
            self.assertNotIn(flag, [f.flag for f in workflow.fields], workflow.id)

    def test_every_field_that_needs_another_names_a_real_one(self) -> None:
        for workflow in WORKFLOWS:
            names = {f.name for f in workflow.fields}
            for field in workflow.fields:
                self.assertTrue(
                    not field.requires or field.requires in names,
                    f"{workflow.id}.{field.name}",
                )

    def test_sign_off_decisions_are_the_ones_the_cli_records(self) -> None:
        decision = next(
            f for f in workflow_named("sign_off").fields if f.name == "decision"
        )
        self.assertEqual([value for value, _ in decision.choices], list(DECISIONS))

    def test_groups_are_contiguous_known_and_in_the_nav_order(self) -> None:
        seen = [w.group for w in WORKFLOWS]
        self.assertTrue(all(seen))
        collapsed = [g for i, g in enumerate(seen) if i == 0 or seen[i - 1] != g]
        self.assertEqual(collapsed, [g for g in GROUPS if g in seen])
        self.assertEqual(set(seen), set(GROUPS))

    def test_outcomes_and_result_tables_are_plain_data(self) -> None:
        for workflow in WORKFLOWS:
            for code, words in workflow.outcomes:
                self.assertIn(code, (0, 1), workflow.id)
                self.assertTrue(words and not words.endswith("."), workflow.id)
        self.assertEqual(len(workflow_named("list_baselines").table), 6)

    def test_every_field_has_plain_language_text(self) -> None:
        for workflow in WORKFLOWS:
            self.assertTrue(workflow.when.startswith("Use this "), workflow.id)
            for field in workflow.fields:
                self.assertTrue(
                    field.label and field.help.endswith("."),
                    f"{workflow.id}.{field.name}",
                )
            if workflow.recorded:
                self.assertTrue(workflow.recorded.endswith("."), workflow.id)

    def test_lookups_read_the_table_being_worked_on(self) -> None:
        self.assertEqual(lookup_source(workflow_named("report")).name, "input")  # type: ignore[union-attr]
        self.assertEqual(lookup_source(workflow_named("diff")).name, "new")  # type: ignore[union-attr]
        self.assertIsNone(lookup_source(workflow_named("comments")))


class GateWorkflowTests(unittest.TestCase):
    def test_check_gate_and_system(self) -> None:
        argv = build_argv(
            workflow_named("check_gate"),
            {
                "input": "r.csv",
                "id_column": "ID",
                "gate": "DDR",
                "system": "SYS-A",
                "config": "c.json",
            },
        )
        self.assertEqual(
            argv,
            [
                "r.csv",
                "--id-column",
                "ID",
                "--config",
                "c.json",
                "--check-gate",
                "DDR",
                "--system",
                "SYS-A",
            ],
        )

    def test_create_baseline_emits_waivers_as_ordered_pairs(self) -> None:
        values = {
            "input": "r.csv",
            "gate": "PDR",
            "user": "Ann",
            "waivers": [
                {"check": "pdr-a", "reason": "Because"},
                {"check": "", "reason": ""},
                {"check": "pdr-b", "reason": "-odd"},
            ],
        }
        argv = build_argv(workflow_named("create_baseline"), values)
        self.assertEqual(
            argv,
            [
                "r.csv",
                "--create-baseline",
                "PDR",
                "--waive",
                "pdr-a",
                "--reason",
                "Because",
                "--waive",
                "pdr-b",
                "--reason=-odd",
                "--user",
                "Ann",
            ],
        )

    def test_a_half_filled_waiver_and_bad_check_ids_are_refused(self) -> None:
        for row in (
            {"check": "pdr-a", "reason": ""},
            {"check": "", "reason": "why"},
            {"check": "a,b", "reason": "why"},
            {"check": "-x", "reason": "why"},
        ):
            with self.subTest(row=row), self.assertRaises(GuiError):
                build_argv(
                    workflow_named("create_baseline"),
                    {"input": "r.csv", "gate": "PDR", "waivers": [row]},
                )
        with self.assertRaises(BadRequest):
            build_argv(
                workflow_named("create_baseline"),
                {"input": "r.csv", "gate": "PDR", "waivers": "pdr-a"},
            )

    def test_sign_off(self) -> None:
        argv = build_argv(
            workflow_named("sign_off"),
            {
                "input": "r.csv",
                "baseline": "PDR-2",
                "role": "Approver",
                "decision": "Approved",
                "note": "Board",
                "evidence": "p.pdf",
            },
        )
        self.assertEqual(
            argv,
            [
                "r.csv",
                "--sign-off",
                "PDR-2",
                "--role",
                "Approver",
                "--decision",
                "Approved",
                "--note",
                "Board",
                "--evidence",
                "p.pdf",
            ],
        )
        with self.assertRaises(BadRequest):
            build_argv(
                workflow_named("sign_off"),
                {"input": "r.csv", "baseline": "B", "role": "R", "decision": "Fine"},
            )

    def test_the_other_gate_commands(self) -> None:
        self.assertEqual(
            build_argv(
                workflow_named("verify_baseline"), {"input": "r.csv", "baseline": "SRR"}
            ),
            ["r.csv", "--verify-baseline", "SRR"],
        )
        self.assertEqual(
            build_argv(workflow_named("list_baselines"), {"input": "r.csv"}),
            ["r.csv", "--list-baselines"],
        )
        self.assertEqual(
            build_argv(
                workflow_named("gate_package"),
                {"input": "r.csv", "baseline": "SRR", "output": "p.html"},
            ),
            ["r.csv", "--gate-package", "SRR", "-o", "p.html"],
        )
        self.assertEqual(
            build_argv(
                workflow_named("import_decisions"),
                {"input": "r.csv", "package": "p.html"},
            ),
            ["r.csv", "--import-decisions", "p.html"],
        )

    def test_embedded_baselines_are_an_advanced_report_and_diff_option(self) -> None:
        self.assertEqual(
            build_argv(workflow_named("report"), {**REPORT, "baselines": "SRR,PDR"})[
                -2:
            ],
            ["--baselines", "SRR,PDR"],
        )
        diff = {"old": "a.csv", "new": "b.csv", "output": "d.html", "baselines": "SRR"}
        self.assertIn("--baselines", build_argv(workflow_named("diff"), diff))

    def test_blocked_check_ids_are_read_from_the_cli_hint(self) -> None:
        err = 'blocked: a fails\nblocked: b fails\nFix the data, or record a waiver: --waive pdr-a,pdr-b --reason "..."\n'
        self.assertEqual(blocked_checks(err), ["pdr-a", "pdr-b"])
        self.assertEqual(blocked_checks("error: nope"), [])

    def test_the_mapping_card_has_no_command_of_its_own(self) -> None:
        with self.assertRaises(BadRequest):
            build_argv(workflow_named("mapping"), {"input": "w.xlsx"})


class GuessIdColumnTests(unittest.TestCase):
    def test_prefers_an_exact_id_then_a_suffix(self) -> None:
        self.assertEqual(guess_id_column(["Name", "Req ID", "id", "Text"]), "id")
        self.assertEqual(guess_id_column(["Name", "Req ID", "Text"]), "Req ID")
        self.assertEqual(guess_id_column(["Name", "test_id"]), "test_id")
        self.assertEqual(guess_id_column(["Name", "ReqId"]), "ReqId")

    def test_no_guess_when_nothing_looks_like_an_id(self) -> None:
        self.assertEqual(guess_id_column(["Name", "Identity", "Valid", "Idle", ""]), "")
        self.assertEqual(guess_id_column([]), "")


class CommandsRunTests(unittest.TestCase):
    def test_every_workflow_builds_a_command_the_cli_accepts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "reqs.csv").write_text(
                "ID,Text\nR1,Hello\nR2,World\n", encoding="utf-8"
            )
            (root / "reqs2.csv").write_text(
                "ID,Text\nR1,Hello again\n", encoding="utf-8"
            )
            write_workbook(root / "book.xlsx")
            cases = {
                "report": {
                    "input": "reqs.csv",
                    "output": "r.html",
                    "id_column": "ID",
                    "document_mode": "develop",
                },
                "develop": {
                    "input": "reqs.csv",
                    "output": "dev.html",
                    "id_column": "ID",
                },
                "diff": {
                    "old": "reqs.csv",
                    "new": "reqs2.csv",
                    "output": "d.html",
                    "id_column": "ID",
                    "initial_diff_view": "side-by-side",
                    "include_unchanged": "on",
                    "document_mode": "develop",
                },
                "to_csv": {
                    "input": str(root / "book.xlsx"),
                    "output": "book.csv",
                    "id_column": "Req ID",
                    "sheet": "Reqs",
                },
                "list_tables": {"workbook": "book.xlsx"},
            }
            for workflow_id, values in cases.items():
                with self.subTest(workflow_id):
                    completed = run_cli(
                        build_argv(workflow_named(workflow_id), values, root), root
                    )
                    self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue((root / "r.html").is_file())
            self.assertIn(
                '"documentMode":"develop"',
                (root / "dev.html").read_text(encoding="utf-8"),
            )
            self.assertTrue((root / "book.csv").is_file())
            extracted = run_cli(
                build_argv(
                    workflow_named("comments"),
                    {"report": "r.html", "output": "c.csv", "comments_format": "text"},
                    root,
                ),
                root,
            )
            self.assertEqual(extracted.returncode, 0, extracted.stderr)
            self.assertTrue((root / "c.csv").is_file())


if __name__ == "__main__":
    unittest.main()
