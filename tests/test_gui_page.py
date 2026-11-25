from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from reqtable.gui_page import SCRIPT, render_page


def script_of(page: str) -> str:
    found = re.search(r"<script>(.*)</script>", page, re.S)
    assert found is not None
    return found.group(1)


NODE = shutil.which("node")

RUNNER = """
const vm = require("vm");
const [script, setup, expression] = process.argv.slice(1);
const context = vm.createContext({ location: { hash: "" }, history: { state: null }, console, sessionStorage: null, localStorage: null, document: { getElementById: () => null }, setTimeout: () => 0, clearTimeout: () => {} });
const result = vm.runInContext(script + "\\n" + setup + "\\n;JSON.stringify(" + expression + ")", context);
process.stdout.write(result === undefined ? "null" : result);
"""


def evaluate(expression: str, setup: str = "") -> object:
    """Run the page script in node, without a DOM and without starting it, then `setup`, and return `expression` as JSON."""
    assert NODE is not None
    done = subprocess.run(
        [NODE, "-e", RUNNER, SCRIPT.replace("__TOKEN__", '"t"'), setup, expression],
        capture_output=True,
        text=True,
    )
    if done.returncode:
        raise AssertionError(done.stderr)
    return json.loads(done.stdout)


class PageTests(unittest.TestCase):
    def test_the_token_is_embedded_and_no_placeholder_is_left(self) -> None:
        page = render_page("abc-123")
        self.assertIn('const TOKEN = "abc-123";', page)
        self.assertNotRegex(page, r"__[A-Z]+__")

    def test_the_page_is_a_home_grid_and_a_wizard_not_three_columns(self) -> None:
        page = render_page("t")
        for gone in ('class="layout"', 'id="nav"', "renderNav", "renderIntro"):
            self.assertNotIn(gone, page)
        for route in ("#/task/", "#/journey/", "hashchange"):
            self.assertIn(route, page)

    @unittest.skipUnless(NODE, "node is not installed")
    def test_the_script_is_valid_javascript(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "page.js"
            path.write_text(script_of(render_page("t")), encoding="utf-8")
            done = subprocess.run(
                ["node", "--check", str(path)], capture_output=True, text=True
            )
        self.assertEqual(done.returncode, 0, done.stderr)


@unittest.skipUnless(NODE, "node is not installed")
class RouteTests(unittest.TestCase):
    def route_of(self, hash: str) -> object:
        return evaluate("parseRoute()", "location.hash = " + json.dumps(hash) + ";")

    def test_a_task_and_a_journey_step_are_read_from_the_hash(self) -> None:
        self.assertEqual(
            self.route_of("#/task/report/options"),
            {"kind": "task", "id": "report", "page": "options"},
        )
        self.assertEqual(
            self.route_of("#/journey/share/2"),
            {"kind": "journey", "jid": "share", "step": 2, "page": ""},
        )

    def test_a_malformed_escape_in_the_hash_goes_home(self) -> None:
        self.assertEqual(self.route_of("#/task/%E0%A4%A"), {"kind": "home"})
        self.assertEqual(self.route_of("#/task/100%"), {"kind": "home"})

    def back_from(self, previous: str) -> object:
        setup = (
            "const calls = []; route = () => calls.push('route');"
            "history.back = () => calls.push('back');"
            "history.replaceState = (s, t, url) => calls.push(url);"
            "history.state = { prev: " + json.dumps(previous) + " };"
            "goBack('#/task/report/files');"
        )
        return evaluate("calls", setup)

    def test_back_returns_to_the_page_before_instead_of_adding_a_history_entry(
        self,
    ) -> None:
        self.assertEqual(self.back_from("#/task/report/files"), ["back"])

    def test_back_replaces_the_entry_when_the_page_before_was_elsewhere(self) -> None:
        self.assertEqual(self.back_from("#/"), ["#/task/report/files", "route"])


STORAGE = (
    "const store = () => { const m = new Map(); return { getItem: (k) => m.has(k) ? m.get(k) : null, setItem: (k, v) => m.set(k, String(v)) }; };"
    "sessionStorage = store(); localStorage = store();"
)


@unittest.skipUnless(NODE, "node is not installed")
class ReloadTests(unittest.TestCase):
    def after_reload(self, before: str, expression: str) -> object:
        """Run `before`, save the session, start again from an empty state as a reload does, and read `expression`."""
        setup = (
            STORAGE
            + before
            + "; persistSession();"
            + "for (const k of SESSION_PARTS) state[k] = {}; restore();"
        )
        return evaluate(expression, setup)

    def test_a_guessed_id_column_is_still_known_as_a_guess_after_a_reload(
        self,
    ) -> None:
        found = self.after_reload(
            "state.values.report = { input: 'a.xlsx', id_column: 'Req ID' };"
            "state.autoId.report = 'Req ID'",
            "[state.values.report, state.autoId]",
        )
        self.assertEqual(
            found, [{"input": "a.xlsx", "id_column": "Req ID"}, {"report": "Req ID"}]
        )

    def test_a_run_result_is_still_there_after_a_reload(self) -> None:
        run = {
            "workflow": "report",
            "values": {"input": "a.csv"},
            "data": {"exit_code": 0},
            "added": True,
        }
        found = self.after_reload(
            "state.runs['task:report'] = " + json.dumps(run), "state.runs"
        )
        self.assertEqual(found, {"task:report": run})


@unittest.skipUnless(NODE, "node is not installed")
class StoredRunTests(unittest.TestCase):
    def runs_after(self, change: str) -> object:
        setup = (
            "state.current = 'report';"
            "state.values = { report: { input: 'a.csv', output: 'r.html' }, compare: { old: 'a.csv' } };"
            "state.runs = {"
            " 'task:report': { workflow: 'report', values: { input: 'a.csv', output: 'r.html' }, data: {} },"
            " 'journey:share:1': { workflow: 'report', values: { input: 'a.csv', output: 'r.html' }, data: {} },"
            " 'task:compare': { workflow: 'compare', values: { old: 'x.csv' }, data: {} } };"
            + change
            + "; refreshPreview();"
        )
        return sorted(evaluate("Object.keys(state.runs)", setup))  # type: ignore[arg-type]

    def test_a_changed_option_drops_the_results_of_that_task_only(self) -> None:
        self.assertEqual(
            self.runs_after("state.values.report.output = 'other.html'"),
            ["task:compare"],
        )

    def test_a_field_that_is_merely_drawn_empty_keeps_the_result(self) -> None:
        self.assertEqual(
            self.runs_after(
                "state.values.report.waivers = []; state.values.report.title = ''"
            ),
            ["journey:share:1", "task:compare", "task:report"],
        )


@unittest.skipUnless(NODE, "node is not installed")
class NextTaskTests(unittest.TestCase):
    def test_the_next_task_starts_from_its_defaults_and_what_ran(self) -> None:
        setup = (
            "go = () => {};"
            "state.workflows = ["
            " { id: 'report', fields: [{ name: 'input' }], table_inputs: ['input'], pages: [{ id: 'files' }] },"
            " { id: 'compare', fields: [{ name: 'old' }, { name: 'new' }, { name: 'output', default: 'changes.html' }],"
            "   table_inputs: ['old', 'new'], pages: [{ id: 'files' }] } ];"
            "state.next = { report: [{ workflow: 'compare', carry: [['input', 'old']] }] };"
            "state.current = 'report';"
            "state.values = { report: { input: 'edited.csv' }, compare: { old: 'x.csv', new: 'y.csv', output: 'mine.html' } };"
            "state.autoId = { compare: 'ID' };"
            "state.runs = { 'task:report': { workflow: 'report', values: { input: 'ran.csv' }, data: {} } };"
            "startNext('compare');"
        )
        self.assertEqual(
            evaluate("[state.values.compare, state.autoId]", setup),
            [{"output": "changes.html", "old": "ran.csv"}, {}],
        )


if __name__ == "__main__":
    unittest.main()
