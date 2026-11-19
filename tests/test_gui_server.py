from __future__ import annotations

import http.client
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import shutil
import unittest
import urllib.request
from pathlib import Path
from urllib.parse import quote, urlsplit

from reqtable.gui_server import TOKEN_HEADER, make_server
from test_xlsx_import import write_workbook
from test_xlsx_mapping import FIXTURE


class ServerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        (self.root / "reqs.csv").write_text("ID,Text\nR1,Hello\nR2,World\n", encoding="utf-8")
        write_workbook(self.root / "book.xlsx")
        self.opened: list[str] = []
        self.server = make_server(self.root, opener=self.opened.append)
        self.port = self.server.server_address[1]
        self.token = self.server.session.token
        thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def call(
        self, method: str, path: str, body: object = None, token: str | None = "default", host: str | None = None,
        content_type: str = "application/json",
    ) -> tuple[int, dict[str, object]]:
        headers = {"Host": host or f"127.0.0.1:{self.port}", "Content-Type": content_type}
        if token is not None:
            headers[TOKEN_HEADER] = self.token if token == "default" else token
        connection = http.client.HTTPConnection("127.0.0.1", self.port)
        try:
            connection.request(method, path, None if body is None else json.dumps(body), headers)
            response = connection.getresponse()
            text = response.read().decode("utf-8")
            return response.status, (json.loads(text) if response.getheader("Content-Type", "").startswith("application/json") else {"text": text})
        finally:
            connection.close()

    def post(self, path: str, body: object, **kwargs: object) -> tuple[int, dict[str, object]]:
        return self.call("POST", path, body, **kwargs)  # type: ignore[arg-type]


class RunTests(ServerTestCase):
    VALUES = {"input": "reqs.csv", "output": "out.html", "id_column": "ID"}

    def test_run_writes_the_report_the_command_preview_describes(self) -> None:
        job = {"workflow": "report", "values": self.VALUES}
        status, preview = self.post("/api/command", job)
        self.assertEqual(status, 200)
        self.assertEqual(preview["argv"], ["reqs.csv", "--id-column", "ID", "-o", "out.html"])
        self.assertIn("python3 ", str(preview["sh"]))
        self.assertTrue(str(preview["powershell"]).startswith("python "))
        status, result = self.post("/api/run", job)
        self.assertEqual((status, result["exit_code"]), (200, 0), result)
        self.assertIn("reqtable-data", (self.root / "out.html").read_text(encoding="utf-8"))
        self.assertEqual(result["outputs"], [str(self.root / "out.html")])

    def test_preview_warns_when_run_would_replace_an_existing_file(self) -> None:
        job = {"workflow": "report", "values": self.VALUES}
        self.assertEqual(self.post("/api/command", job)[1]["replaces"], [])
        self.post("/api/run", job)
        self.assertEqual(self.post("/api/command", job)[1]["replaces"], ["out.html"])

    def test_a_failed_run_returns_the_cli_error(self) -> None:
        status, result = self.post("/api/run", {"workflow": "report", "values": {**self.VALUES, "id_column": "Nope"}})
        self.assertEqual(status, 200)
        self.assertEqual(result["exit_code"], 3)
        self.assertIn("error: ", str(result["stderr"]))
        self.assertEqual(result["outputs"], [])
        self.assertFalse((self.root / "out.html").exists())

    def test_incomplete_form_is_an_error_message_not_a_run(self) -> None:
        status, result = self.post("/api/command", {"workflow": "report", "values": {"input": "reqs.csv"}})
        self.assertEqual(status, 200)
        self.assertIn("Save the report as", str(result["error"]))

    def test_only_reports_this_session_wrote_can_be_opened(self) -> None:
        stray = self.root / "stray.html"
        stray.write_text("<p>x</p>", encoding="utf-8")
        self.assertEqual(self.post("/api/open", {"path": str(stray)})[0], 400)
        self.post("/api/run", {"workflow": "report", "values": self.VALUES})
        status, _ = self.post("/api/open", {"path": str(self.root / "out.html")})
        self.assertEqual(status, 200)
        self.assertEqual(self.opened, [(self.root / "out.html").as_uri()])

    def test_script_is_built_from_the_same_steps(self) -> None:
        steps = [{"workflow": "report", "values": self.VALUES}, {"workflow": "list_tables", "values": {"workbook": "book.xlsx"}}]
        status, result = self.post("/api/script", {"steps": steps, "shell": "powershell"})
        self.assertEqual(status, 200)
        self.assertEqual(result["filename"], "reqtable-workflow.ps1")
        self.assertIn("python -m reqtable reqs.csv --id-column ID -o out.html", str(result["script"]))
        self.assertIn("--list-tables book.xlsx", str(result["script"]))
        self.assertEqual(self.post("/api/script", {"steps": steps, "shell": "cmd"})[0], 400)


class LookupTests(ServerTestCase):
    def test_workflows_come_from_the_registry(self) -> None:
        status, result = self.call("GET", "/api/workflows")
        self.assertEqual(status, 200)
        ids = [w["id"] for w in result["workflows"]]  # type: ignore[index]
        self.assertEqual([w["id"] for w in result["workflows"] if w["group"] == "Excel workbooks"], ["list_tables", "to_csv", "mapping"])  # type: ignore[index]
        self.assertEqual(ids[:2], ["report", "develop"])
        self.assertEqual(result["workdir"], str(self.root))

    def test_browse_lists_folders_first_and_filters_files_by_extension(self) -> None:
        (self.root / "sub").mkdir()
        (self.root / "notes.txt").write_text("x", encoding="utf-8")
        (self.root / ".hidden").mkdir()
        status, result = self.call("GET", f"/api/browse?path={quote(str(self.root))}&ext=.csv,.xlsx")
        self.assertEqual(status, 200)
        self.assertEqual([e["name"] for e in result["entries"]], ["sub", "book.xlsx", "reqs.csv"])  # type: ignore[index]
        self.assertEqual(result["parent"], str(self.root.parent))
        status, result = self.call("GET", "/api/browse")
        self.assertEqual(result["path"], str(self.root))
        self.assertEqual([e["name"] for e in result["entries"]], ["sub"])  # type: ignore[index]
        self.assertIn("error", self.call("GET", f"/api/browse?path={quote(str(self.root / 'reqs.csv'))}")[1])

    def test_columns_of_a_csv_honour_the_delimiter_and_preview_the_rows(self) -> None:
        (self.root / "semi.csv").write_text("ID;Text\nR1;x\n", encoding="utf-8")
        found = self.call("GET", "/api/columns?path=reqs.csv")[1]
        self.assertEqual(found, {"columns": ["ID", "Text"], "row_count": 2, "rows": [["R1", "Hello"], ["R2", "World"]], "id_guess": "ID"})
        self.assertEqual(self.call("GET", "/api/columns?path=semi.csv&delimiter=%3B")[1]["columns"], ["ID", "Text"])

    def test_the_preview_shows_three_rows_and_counts_the_rest(self) -> None:
        body = "".join(f"R{i},Row {i}\n" for i in range(1, 8)) + ",\n"
        (self.root / "long.csv").write_text("Req ID,Text\n" + body, encoding="utf-8")
        found = self.call("GET", "/api/columns?path=long.csv")[1]
        self.assertEqual((found["row_count"], len(found["rows"]), found["id_guess"]), (7, 3, "Req ID"))  # type: ignore[arg-type]

    def test_columns_of_a_workbook_follow_the_chosen_sheet(self) -> None:
        status, result = self.call("GET", "/api/columns?path=book.xlsx&sheet=Reqs")
        self.assertEqual(result["columns"], ["Req ID", "Req Type", "Requirement", "Owner", "Category"])
        self.assertEqual((result["id_guess"], result["row_count"], len(result["rows"])), ("Req ID", 7, 3))  # type: ignore[arg-type]
        status, result = self.call("GET", "/api/columns?path=book.xlsx")
        self.assertEqual(result["columns"], [])
        self.assertIn("--table", str(result["error"]))

    def test_columns_of_a_multi_table_workbook_need_a_table_and_then_preview_it(self) -> None:
        shutil.copy(FIXTURE, self.root / "sample.xlsx")
        self.assertIn("error", self.call("GET", "/api/columns?path=sample.xlsx")[1])
        found = self.call("GET", "/api/columns?path=sample.xlsx&table=Requirements")[1]
        self.assertEqual((found["columns"][:2], found["id_guess"], found["row_count"]), (["ID", "Requirement"], "ID", 4))  # type: ignore[index]

    def test_tables_lists_sheets_and_tables(self) -> None:
        status, result = self.call("GET", "/api/tables?path=book.xlsx")
        self.assertEqual(result["sheets"], [{"name": "Reqs", "state": "visible"}])
        self.assertEqual(result["tables"], [])
        self.assertIn("error", self.call("GET", "/api/tables?path=reqs.csv")[1])

    def test_page_needs_the_token_in_the_address(self) -> None:
        self.assertEqual(self.call("GET", "/")[0], 403)
        status, result = self.call("GET", f"/?token={self.token}")
        self.assertEqual(status, 200)
        self.assertIn(self.token, str(result["text"]))


TRACE_CSV = (
    "ID,Type,Name,Requirement,Part of,Priority,Verification Method,Verification Level\n"
    "SYS-A,System,Reqtable,,,,,\n"
    "SYS-B,System,Exporter,,SYS-A,,,\n"
    "REQ-1,Requirement,,Shall export CSV.,,Must,Test,\n"
)
GATE = {
    "id": "G1", "name": "Gate one", "scope": "table", "includes": ["Requirement", "System"], "captures_status": False,
    "checks": [{"id": "g1-level", "description": "Every requirement has a verification level", "filled": "Verification Level"}],
    "signoff": [{"role": "Approver", "min": 1}],
}


def files_config(*, enforcement: str = "advisory") -> dict[str, object]:
    return {"id_column": "ID", "traceability": True, "gates": [GATE], "baselines": {"store": "files", "enforcement": enforcement}}


class GateTests(ServerTestCase):
    def setUp(self) -> None:
        super().setUp()
        (self.root / "trace.csv").write_text(TRACE_CSV, encoding="utf-8")
        (self.root / "files.json").write_text(json.dumps(files_config()), encoding="utf-8")
        (self.root / "strict.json").write_text(json.dumps(files_config(enforcement="strict")), encoding="utf-8")

    def values(self, **extra: object) -> dict[str, object]:
        return {"input": "trace.csv", "config": "files.json", **extra}

    def run_job(self, workflow: str, **values: object) -> dict[str, object]:
        status, result = self.post("/api/run", {"workflow": workflow, "values": self.values(**values)})
        self.assertEqual(status, 200, result)
        return result

    def test_gates_come_from_the_settings_file_with_roles_and_checks(self) -> None:
        found = self.call("GET", "/api/gates?config=files.json")[1]
        self.assertEqual(
            found["gates"],
            [{
                "id": "G1", "name": "Gate one", "scope": "table", "roles": [{"role": "Approver", "min": 1}],
                "checks": [{"id": "g1-level", "description": "Every requirement has a verification level", "enforcement": "advisory"}],
            }],
        )
        strict = self.call("GET", "/api/gates?config=strict.json")[1]
        self.assertEqual(strict["gates"][0]["checks"][0]["enforcement"], "strict")  # type: ignore[index]
        default = self.call("GET", "/api/gates")[1]
        self.assertEqual([g["id"] for g in default["gates"][:2]], ["SRR", "SFR"])  # type: ignore[index]
        self.assertIn("error", self.call("GET", "/api/gates?config=missing.json")[1])

    def test_systems_come_from_the_table(self) -> None:
        found = self.call("GET", "/api/systems?path=trace.csv&config=files.json")[1]
        self.assertEqual(found["systems"], [{"id": "SYS-A", "name": "Reqtable"}, {"id": "SYS-B", "name": "Exporter"}])
        self.assertEqual(self.call("GET", "/api/systems?path=")[1], {"systems": []})
        self.assertIn("error", self.call("GET", "/api/systems?path=trace.csv")[1])

    def test_baselines_are_listed_after_one_is_frozen(self) -> None:
        self.assertEqual(self.call("GET", "/api/baselines?path=trace.csv&config=files.json")[1]["baselines"], [])
        created = self.run_job("create_baseline", gate="G1")
        self.assertEqual(created["exit_code"], 0, created)
        self.assertIn("Created baseline G1", str(created["stdout"]))
        found = self.call("GET", "/api/baselines?path=trace.csv&config=files.json")[1]
        self.assertEqual([(b["name"], b["gate"], b["system"]) for b in found["baselines"]], [("G1", "G1", "")])  # type: ignore[index]
        self.assertTrue(found["baselines"][0]["created_by"])  # type: ignore[index]
        listed = self.run_job("list_baselines")
        self.assertTrue(str(listed["stdout"]).startswith("G1\tG1\t-\t"), listed)

    def test_the_git_store_explains_itself_outside_a_repository(self) -> None:
        found = self.call("GET", "/api/baselines?path=trace.csv")[1]
        self.assertEqual(found["baselines"], [])
        self.assertIn("git", str(found["error"]))

    def test_check_gate_not_ready_is_exit_1_with_the_check_lines(self) -> None:
        result = self.run_job("check_gate", gate="G1")
        self.assertEqual(result["exit_code"], 1)
        self.assertIn("g1-level", str(result["stdout"]))

    def test_freeze_sign_off_and_verify_loop(self) -> None:
        self.assertEqual(self.run_job("create_baseline", gate="G1")["exit_code"], 0)
        not_yet = self.run_job("verify_baseline", baseline="G1")
        self.assertEqual(not_yet["exit_code"], 1)
        self.assertIn("Approver", str(not_yet["stdout"]))
        signed = self.run_job("sign_off", baseline="G1", role="Approver", decision="Approved", user="Casey", note="Board")
        self.assertEqual(signed["exit_code"], 0, signed)
        self.assertIn("Recorded Approved by Casey as Approver for G1", str(signed["stdout"]))
        done = self.run_job("verify_baseline", baseline="G1")
        self.assertEqual(done["exit_code"], 0, done)
        package = self.run_job("gate_package", baseline="G1", output="package.html")
        self.assertEqual(package["exit_code"], 0, package)
        self.assertEqual(package["outputs"], [str(self.root / "package.html")])

    def test_a_blocked_freeze_names_the_checks_to_waive_and_a_waiver_unblocks_it(self) -> None:
        blocked = self.run_job("create_baseline", config="strict.json", gate="G1")
        self.assertEqual((blocked["exit_code"], blocked["blocked"]), (1, ["g1-level"]))
        self.assertEqual(self.call("GET", "/api/baselines?path=trace.csv&config=strict.json")[1]["baselines"], [])
        waived = self.run_job(
            "create_baseline", config="strict.json", gate="G1", waivers=[{"check": "g1-level", "reason": "Levels arrive at PDR"}]
        )
        self.assertEqual(waived["exit_code"], 0, waived)
        self.assertIn("Waived g1-level", str(waived["stdout"]))

    def test_a_run_that_fails_for_another_reason_offers_no_waivers(self) -> None:
        result = self.run_job("create_baseline", gate="NOPE")
        self.assertEqual((result["exit_code"], result["blocked"]), (2, []))

    def test_import_decisions_runs_through_the_same_command(self) -> None:
        self.run_job("create_baseline", gate="G1")
        self.run_job("gate_package", baseline="G1", output="package.html")
        result = self.run_job("import_decisions", package="package.html")
        self.assertEqual(result["exit_code"], 0, result)

    @unittest.skipUnless(shutil.which("git"), "needs git")
    def test_a_baseline_in_a_git_repository(self) -> None:
        def git(*args: str) -> None:
            subprocess.run(["git", "-C", str(self.root), "-c", "user.name=T", "-c", "user.email=t@example.com", *args], check=True, capture_output=True)

        git("init", "-q")
        git("add", "trace.csv", "files.json")
        git("commit", "-q", "-m", "data")
        (self.root / "git.json").write_text(json.dumps({**files_config(), "baselines": {"store": "git"}}), encoding="utf-8")
        values = {"config": "git.json", "gate": "G1"}
        created = self.run_job("create_baseline", **values)
        self.assertEqual(created["exit_code"], 0, created)
        found = self.call("GET", "/api/baselines?path=trace.csv&config=git.json")[1]
        self.assertEqual([b["name"] for b in found["baselines"]], ["G1"])  # type: ignore[index]


class SecurityTests(ServerTestCase):
    def test_api_requires_the_token(self) -> None:
        self.assertEqual(self.call("GET", "/api/workflows", token=None)[0], 403)
        self.assertEqual(self.call("GET", "/api/workflows", token="wrong")[0], 403)
        self.assertEqual(self.post("/api/run", {"workflow": "report", "values": {}}, token=None)[0], 403)

    def test_bad_host_is_refused_even_with_the_token(self) -> None:
        for host in ("evil.example", f"evil.example:{self.port}", "127.0.0.1", f"localhost:{self.port + 1}"):
            with self.subTest(host=host):
                self.assertEqual(self.call("GET", "/api/workflows", host=host)[0], 403)
                self.assertEqual(self.call("GET", f"/?token={self.token}", host=host)[0], 403)
        self.assertEqual(self.call("GET", "/api/workflows", host=f"localhost:{self.port}")[0], 200)

    def test_only_json_bodies_are_accepted(self) -> None:
        job = {"workflow": "list_tables", "values": {"workbook": "book.xlsx"}}
        self.assertEqual(self.post("/api/command", job, content_type="text/plain")[0], 400)
        self.assertEqual(self.post("/api/command", job, content_type="application/x-www-form-urlencoded")[0], 400)

    def test_unknown_workflow_field_and_choice_are_400(self) -> None:
        self.assertEqual(self.post("/api/run", {"workflow": "nope", "values": {}})[0], 400)
        self.assertEqual(self.post("/api/run", {"workflow": "report", "values": {"input": "reqs.csv", "evil": "x"}})[0], 400)
        self.assertEqual(self.post("/api/run", {"workflow": "report", "values": {"document_mode": "x"}})[0], 400)
        self.assertEqual(self.post("/api/run", ["not", "an", "object"])[0], 400)
        self.assertEqual(self.post("/api/nope", {})[0], 404)

    def test_server_listens_on_loopback_only(self) -> None:
        self.assertEqual(urlsplit(self.server.url).hostname, "127.0.0.1")
        self.assertEqual(self.server.server_address[0], "127.0.0.1")


class GuiFlagTests(unittest.TestCase):
    def launch(self, *flags: str, cwd: str) -> subprocess.Popen[str]:
        here = Path(__file__).resolve().parent.parent
        return subprocess.Popen(
            [sys.executable, "-m", "reqtable", *flags], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env={**os.environ, "PYTHONPATH": str(here)},
        )

    @unittest.skipIf(os.name == "nt", "needs POSIX SIGINT")
    def test_gui_serves_the_page_and_stops_cleanly_on_ctrl_c(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            process = self.launch("--gui", "--no-browser", cwd=directory)
            try:
                assert process.stdout is not None
                first = process.stdout.readline().strip()
                self.assertTrue(first.startswith("reqtable GUI running at http://127.0.0.1:"), first)
                self.assertIn("?token=", first)
                self.assertEqual(process.stdout.readline().strip(), "Press Ctrl+C to stop")
                with urllib.request.urlopen(first.rsplit(" ", 1)[1]) as response:
                    self.assertIn("reqtable", response.read().decode("utf-8"))
                process.send_signal(signal.SIGINT)
                self.assertEqual(process.wait(timeout=10), 0, process.stderr.read() if process.stderr else "")
            finally:
                process.kill()
                process.wait()
                for stream in (process.stdout, process.stderr):
                    if stream:
                        stream.close()

    def test_no_browser_alone_is_a_usage_error_and_no_arguments_still_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            for flags in (("--no-browser",), ()):
                done = self.launch(*flags, cwd=directory)
                _, error = done.communicate(timeout=20)
                self.assertEqual(done.returncode, 2, flags)
                self.assertIn("error:", error)


if __name__ == "__main__":
    unittest.main()
