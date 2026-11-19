"""Local web server for the GUI: a thin, token-guarded shell over reqtable.gui."""
from __future__ import annotations

import hmac
import json
import os
import secrets
import subprocess
import threading
import webbrowser
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlsplit

from . import gui_lookups
from .gui_mapping import build_mapping, load_mapping, mapping_json, preview_mapping, role_named, save_mapping, suggest_columns
from .gui import (
    WORKFLOWS, BadRequest, GuiError, Launcher, Workflow, blocked_checks, build_argv, column_source, launcher, lookup_source,
    posix_command, powershell_command, script, workflow_named,
)
from .gui_page import render_page

TOKEN_HEADER = "X-Reqtable-Token"
RUN_TIMEOUT_SECONDS = 300
MAX_BODY_BYTES = 1_000_000
SCRIPT_NAMES = {"sh": "reqtable-workflow.sh", "powershell": "reqtable-workflow.ps1"}


class Session:
    """State shared by every request of one GUI process."""

    def __init__(self, workdir: Path, opener: Callable[[str], object]) -> None:
        self.workdir = workdir
        self.token = secrets.token_urlsafe(24)
        self.launcher: Launcher = launcher(workdir)
        self.opener = opener
        self.openable: set[Path] = set()
        self.lock = threading.Lock()

    def command(self, workflow: Workflow, values: dict[str, Any]) -> dict[str, Any]:
        argv = build_argv(workflow, values, self.workdir)
        return {
            "argv": argv,
            "sh": posix_command(argv, self.launcher.shown),
            "powershell": powershell_command(argv, self.launcher.shown),
            "replaces": [str(value) for value in self.saved_values(workflow, values) if (self.workdir / value).exists()],
        }

    @staticmethod
    def saved_values(workflow: Workflow, values: dict[str, Any]) -> list[str]:
        return [
            value for field in workflow.fields if field.kind == "save" and (value := str(values.get(field.name, "")).strip())
        ]

    def run(self, workflow: Workflow, values: dict[str, Any]) -> dict[str, Any]:
        argv = build_argv(workflow, values, self.workdir)
        env = {**os.environ, **self.launcher.env, "PYTHONIOENCODING": "utf-8"}
        try:
            done = subprocess.run(
                [*self.launcher.run, *argv], cwd=self.workdir, env=env, capture_output=True, text=True,
                encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=RUN_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return {"exit_code": None, "stdout": "", "stderr": f"error: stopped after {RUN_TIMEOUT_SECONDS} seconds", "outputs": [], "blocked": []}
        written = [self.workdir / value for value in self.saved_values(workflow, values) if done.returncode == 0 and (self.workdir / value).is_file()]
        with self.lock:
            self.openable.update(path.resolve() for path in written if path.suffix.lower() == ".html")
        return {
            "exit_code": done.returncode, "stdout": done.stdout, "stderr": done.stderr, "outputs": [str(p) for p in written],
            "blocked": blocked_checks(done.stderr) if done.returncode == 1 else [],
        }

    def open_report(self, path: str) -> None:
        target = Path(path).resolve()
        with self.lock:
            allowed = target in self.openable
        if not allowed or not target.is_file():
            raise BadRequest("that file was not produced by this session")
        self.opener(target.as_uri())

    def browse(self, path: str, extensions: tuple[str, ...]) -> dict[str, Any]:
        folder = (self.workdir / Path(path).expanduser()).resolve() if path else self.workdir
        try:
            children = sorted(folder.iterdir(), key=lambda p: p.name.lower())
        except (OSError, NotADirectoryError) as exc:
            raise GuiError(f"cannot open folder {folder}: {exc.strerror or exc}") from exc
        entries = []
        for child in children:
            if child.name.startswith("."):
                continue
            try:
                is_dir = child.is_dir()
            except OSError:
                continue
            if is_dir or "*" in extensions or (extensions and child.suffix.lower() in extensions):
                entries.append({"name": child.name, "path": str(child), "dir": is_dir})
        entries.sort(key=lambda e: not e["dir"])
        parent = folder.parent
        return {
            "path": str(folder),
            "parent": str(parent) if parent != folder else None,
            "entries": entries,
            "places": [
                {"name": "Working folder", "path": str(self.workdir)},
                {"name": "Home", "path": str(Path.home())},
            ],
        }

    def mapping_preview(self, body: dict[str, Any]) -> dict[str, Any]:
        mapping = build_mapping(body.get("form"))  # type: ignore[arg-type]
        return {"mapping": mapping, **preview_mapping(self.workdir / str(body.get("path", "")), mapping)}

    def mapping_save(self, body: dict[str, Any]) -> dict[str, Any]:
        mapping = build_mapping(body.get("form"))  # type: ignore[arg-type]
        return {"mapping": mapping, **save_mapping(self.workdir, str(body.get("path", "")), mapping, body.get("overwrite") is True)}

    def mapping_suggest(self, query: dict[str, str]) -> dict[str, Any]:
        found = gui_lookups.columns(self.workdir, query)
        if "error" in found:
            return {"columns": [], "id_prefix": "", "error": found["error"]}
        return suggest_columns(role_named(query.get("role", "")), found["columns"])

    def script(self, steps: object, shell: object) -> dict[str, Any]:
        if shell not in SCRIPT_NAMES:
            raise BadRequest("shell must be 'sh' or 'powershell'")
        if not isinstance(steps, list):
            raise BadRequest("steps must be a list")
        built = []
        for step in steps:
            workflow, values = parse_job(step)
            note = step.get("note", "") if isinstance(step, dict) else ""
            if not isinstance(note, str):
                raise BadRequest("note must be text")
            built.append((f"{workflow.title} ({note})" if note else workflow.title, build_argv(workflow, values, self.workdir)))
        return {"script": script(built, shell, self.workdir, self.launcher.shown), "filename": SCRIPT_NAMES[shell]}


def parse_job(body: object) -> tuple[Workflow, dict[str, Any]]:
    if not isinstance(body, dict) or not isinstance(body.get("workflow"), str) or not isinstance(body.get("values", {}), dict):
        raise BadRequest("expected {workflow, values}")
    return workflow_named(body["workflow"]), body.get("values", {})


class Handler(BaseHTTPRequestHandler):
    server: "GuiServer"

    def log_message(self, format: str, *args: object) -> None:
        pass

    @property
    def session(self) -> Session:
        return self.server.session

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        self.send_bytes(status, json.dumps(payload).encode("utf-8"), "application/json")

    def send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def host_allowed(self) -> bool:
        port = self.server.server_address[1]
        return self.headers.get("Host") in (f"127.0.0.1:{port}", f"localhost:{port}")

    def token_ok(self, supplied: str | None) -> bool:
        return supplied is not None and hmac.compare_digest(supplied.encode(), self.session.token.encode())

    def refuse(self, status: HTTPStatus, message: str) -> None:
        self.send_json(status, {"error": message})

    def do_GET(self) -> None:
        if not self.host_allowed():
            return self.refuse(HTTPStatus.FORBIDDEN, "unexpected Host header")
        url = urlsplit(self.path)
        query = {key: values[0] for key, values in parse_qs(url.query, keep_blank_values=True).items()}
        if url.path == "/":
            if not self.token_ok(query.get("token")):
                return self.send_bytes(HTTPStatus.FORBIDDEN, b"Open the address that reqtable --gui printed, including ?token=...", "text/plain")
            return self.send_bytes(HTTPStatus.OK, render_page(self.session.token).encode("utf-8"), "text/html")
        if not url.path.startswith("/api/"):
            return self.refuse(HTTPStatus.NOT_FOUND, "not found")
        if not self.token_ok(self.headers.get(TOKEN_HEADER)):
            return self.refuse(HTTPStatus.FORBIDDEN, "missing or wrong token")
        routes: dict[str, Callable[[], dict[str, Any]]] = {
            "/api/workflows": lambda: {"workflows": workflows_json(), "workdir": str(self.session.workdir), "mapping": mapping_json()},
            "/api/browse": lambda: self.session.browse(
                query.get("path", ""), tuple(e for e in query.get("ext", "").lower().split(",") if e)
            ),
            "/api/columns": lambda: gui_lookups.columns(self.session.workdir, query),
            "/api/tables": lambda: gui_lookups.tables(self.session.workdir, query.get("path", "")),
            "/api/gates": lambda: gui_lookups.gates(self.session.workdir, query),
            "/api/baselines": lambda: gui_lookups.baselines(self.session.workdir, query),
            "/api/systems": lambda: gui_lookups.systems(self.session.workdir, query),
            "/api/mapping/suggest": lambda: self.session.mapping_suggest(query),
            "/api/mapping/load": lambda: load_mapping(self.session.workdir, query.get("path", "")),
        }
        self.dispatch(routes.get(url.path))

    def do_POST(self) -> None:
        if not self.host_allowed():
            return self.refuse(HTTPStatus.FORBIDDEN, "unexpected Host header")
        path = urlsplit(self.path).path
        if not path.startswith("/api/"):
            return self.refuse(HTTPStatus.NOT_FOUND, "not found")
        if not self.token_ok(self.headers.get(TOKEN_HEADER)):
            return self.refuse(HTTPStatus.FORBIDDEN, "missing or wrong token")
        if (self.headers.get("Content-Type") or "").split(";")[0].strip() != "application/json":
            return self.refuse(HTTPStatus.BAD_REQUEST, "send JSON with Content-Type: application/json")
        declared = (self.headers.get("Content-Length") or "").strip()
        if not declared.isdigit():
            return self.refuse(HTTPStatus.BAD_REQUEST, "send a Content-Length header with the size of the body")
        length = int(declared)
        if length > MAX_BODY_BYTES:
            return self.refuse(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "request too large")
        try:
            body = json.loads(self.rfile.read(length) or b"null")
        except (ValueError, UnicodeError):
            return self.refuse(HTTPStatus.BAD_REQUEST, "body is not valid JSON")
        session = self.session

        def command() -> dict[str, Any]:
            return session.command(*parse_job(body))

        def run() -> dict[str, Any]:
            return session.run(*parse_job(body))

        def open_file() -> dict[str, Any]:
            if not isinstance(body, dict) or not isinstance(body.get("path"), str):
                raise BadRequest("expected {path}")
            session.open_report(body["path"])
            return {"ok": True}

        def make_script() -> dict[str, Any]:
            if not isinstance(body, dict):
                raise BadRequest("expected {steps, shell}")
            return session.script(body.get("steps"), body.get("shell"))

        def mapping(action: Callable[[dict[str, Any]], dict[str, Any]]) -> Callable[[], dict[str, Any]]:
            def handler() -> dict[str, Any]:
                if not isinstance(body, dict):
                    raise BadRequest("expected {path, form}")
                return action(body)

            return handler

        routes = {
            "/api/command": command, "/api/run": run, "/api/open": open_file, "/api/script": make_script,
            "/api/mapping/preview": mapping(session.mapping_preview), "/api/mapping/save": mapping(session.mapping_save),
        }
        self.dispatch(routes.get(path))

    def dispatch(self, route: Callable[[], dict[str, Any]] | None) -> None:
        if route is None:
            return self.refuse(HTTPStatus.NOT_FOUND, "not found")
        try:
            self.send_json(HTTPStatus.OK, route())
        except BadRequest as exc:
            self.refuse(HTTPStatus.BAD_REQUEST, str(exc))
        except GuiError as exc:
            self.send_json(HTTPStatus.OK, {"error": str(exc)})
        except Exception as exc:
            self.refuse(HTTPStatus.INTERNAL_SERVER_ERROR, f"unexpected error: {exc}")


class GuiServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, session: Session, port: int) -> None:
        super().__init__(("127.0.0.1", port), Handler)
        self.session = session

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}/?token={self.session.token}"


def workflows_json() -> list[dict[str, Any]]:
    result = []
    for workflow in WORKFLOWS:
        source = column_source(workflow)
        lookup = lookup_source(workflow)
        result.append({
            **asdict(workflow), "column_source": source.name if source else "", "lookup_input": lookup.name if lookup else "",
        })
    return result


def make_server(workdir: Path, port: int = 0, opener: Callable[[str], object] = webbrowser.open) -> GuiServer:
    return GuiServer(Session(Path(workdir).resolve(), opener), port)


def serve(workdir: Path, open_browser: bool, port: int = 0) -> int:
    server = make_server(workdir, port)
    print(f"reqtable GUI running at {server.url}", flush=True)
    print("Press Ctrl+C to stop", flush=True)
    if open_browser:
        threading.Thread(target=webbrowser.open, args=(server.url,), daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0
