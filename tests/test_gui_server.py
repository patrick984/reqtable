from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import quote, urlsplit

from reqtable.gui_server import TOKEN_HEADER, make_server
from test_xlsx_import import write_workbook


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
        self.assertEqual(preview["argv"], ["reqs.csv", "-o", "out.html", "--id-column", "ID"])
        self.assertIn("python3 ", str(preview["sh"]))
        self.assertTrue(str(preview["powershell"]).startswith("python "))
        status, result = self.post("/api/run", job)
        self.assertEqual((status, result["exit_code"]), (200, 0), result)
        self.assertIn("reqtable-data", (self.root / "out.html").read_text(encoding="utf-8"))
        self.assertEqual(result["outputs"], [str(self.root / "out.html")])

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
        self.assertIn("python -m reqtable reqs.csv -o out.html --id-column ID", str(result["script"]))
        self.assertIn("--list-tables book.xlsx", str(result["script"]))
        self.assertEqual(self.post("/api/script", {"steps": steps, "shell": "cmd"})[0], 400)


class LookupTests(ServerTestCase):
    def test_workflows_come_from_the_registry(self) -> None:
        status, result = self.call("GET", "/api/workflows")
        self.assertEqual(status, 200)
        ids = [w["id"] for w in result["workflows"]]  # type: ignore[index]
        self.assertEqual(ids, ["report", "diff", "comments", "list_tables", "to_csv"])
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

    def test_columns_of_a_csv_honour_the_delimiter(self) -> None:
        (self.root / "semi.csv").write_text("ID;Text\nR1;x\n", encoding="utf-8")
        self.assertEqual(self.call("GET", "/api/columns?path=reqs.csv")[1], {"columns": ["ID", "Text"]})
        self.assertEqual(self.call("GET", "/api/columns?path=semi.csv&delimiter=%3B")[1], {"columns": ["ID", "Text"]})

    def test_columns_of_a_workbook_follow_the_chosen_sheet(self) -> None:
        status, result = self.call("GET", "/api/columns?path=book.xlsx&sheet=Reqs")
        self.assertEqual(result["columns"], ["Req ID", "Req Type", "Requirement", "Owner", "Category"])
        status, result = self.call("GET", "/api/columns?path=book.xlsx")
        self.assertEqual(result["columns"], [])
        self.assertIn("--table", str(result["error"]))

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


if __name__ == "__main__":
    unittest.main()
