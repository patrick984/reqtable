from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from reqtable.baselines import (
    BaselineName,
    FileStore,
    Gate,
    GitStore,
    Manifest,
    content_hash,
    create_baseline,
    next_name,
    open_store,
    resolve,
    select_scope,
    sort_manifests,
)
from reqtable.core import DEFAULT_CONFIG, ConfigError, InputError, load_config, read_csv_table, validate_config

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "baseline_scope.json").read_text(encoding="utf-8"))


def config_with(**changes: object) -> dict:
    return {**copy.deepcopy(DEFAULT_CONFIG), **changes}


def write_config(test: unittest.TestCase, content: dict) -> str:
    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    path = Path(tmp.name) / "config.json"
    path.write_text(json.dumps(content), encoding="utf-8")
    return str(path)


class ConfigTests(unittest.TestCase):
    def test_default_config_is_valid_and_has_preset_gates(self) -> None:
        validate_config(copy.deepcopy(DEFAULT_CONFIG))
        gates = [Gate.from_config(g) for g in DEFAULT_CONFIG["gates"]]
        self.assertEqual([g.id for g in gates], ["SRR", "SFR", "PDR", "DDR", "CDR", "TRR", "SVR", "FCA", "PCA"])
        by_id = {g.id: g for g in gates}
        self.assertEqual(by_id["DDR"].scope, "system")
        self.assertEqual(by_id["TRR"].includes, ("Requirement", "System", "Test", "Test plan"))
        self.assertEqual([g.id for g in gates if g.captures_status], ["SVR", "FCA", "PCA"])
        self.assertEqual(by_id["PCA"].produces, "As-built product baseline")
        self.assertEqual(sum(g.scope == "system" for g in gates), 1)

    def test_user_gates_replace_the_preset(self) -> None:
        config = load_config(write_config(self, {"gates": [{"id": "ALPHA"}]}))
        self.assertEqual([g["id"] for g in config["gates"]], ["ALPHA"])
        self.assertEqual(Gate.from_config(config["gates"][0]).includes, ("Requirement", "System"))

    def test_partial_baselines_config_keeps_other_defaults(self) -> None:
        config = load_config(write_config(self, {"baselines": {"store": "files", "git": {"tag_prefix": "bl/"}}}))
        self.assertEqual(config["baselines"]["files"], {"directory": "baselines"})
        self.assertEqual(config["baselines"]["git"]["tag_prefix"], "bl/")

    def assertRejected(self, config: dict, fragment: str) -> None:
        with self.assertRaises(ConfigError) as caught:
            validate_config(config)
        self.assertIn(fragment, str(caught.exception))

    def baselines(self, **changes: object) -> dict:
        config = copy.deepcopy(DEFAULT_CONFIG)
        config["baselines"].update(changes)
        return config

    def gates(self, *gates: dict) -> dict:
        return config_with(gates=list(gates))

    def test_rejects_bad_baselines_settings(self) -> None:
        self.assertRejected(self.baselines(store="svn"), "baselines.store")
        self.assertRejected(self.baselines(git={"tag_prefix": "baseline"}), "tag_prefix")
        self.assertRejected(self.baselines(git={"tag_prefix": ""}), "tag_prefix")
        self.assertRejected(self.baselines(files={"directory": " "}), "directory")
        self.assertRejected(self.baselines(enforcement="strict"), "enforcement")
        self.assertRejected(self.baselines(status_columns="Compliance"), "status_columns")
        self.assertRejected(self.baselines(status_columns=[1]), "status_columns")

    def test_rejects_bad_gates(self) -> None:
        self.assertRejected(config_with(gates={"id": "X"}), "gates must be an array")
        self.assertRejected(self.gates({"name": "No id"}), "id")
        self.assertRejected(self.gates({"id": ""}), "id")
        self.assertRejected(self.gates({"id": "A/B"}), "'/'")
        self.assertRejected(self.gates({"id": "SRR-2"}), "re-baselines")
        self.assertRejected(self.gates({"id": "A"}, {"id": "A"}), "duplicate")
        self.assertRejected(self.gates({"id": "A", "scope": "program"}), "scope")
        self.assertRejected(self.gates({"id": "A", "includes": []}), "includes")
        self.assertRejected(self.gates({"id": "A", "includes": ["Widget"]}), "includes")
        self.assertRejected(self.gates({"id": "A", "captures_status": "yes"}), "captures_status")
        self.assertRejected(self.gates({"id": "A", "colour": "red"}), "gates[0].colour")

    def test_gate_checks_and_signoff_are_accepted_and_ignored(self) -> None:
        validate_config(self.gates({"id": "A", "checks": [{"id": "x"}], "signoff": [{"role": "Approver"}]}))
        self.assertRejected(self.gates({"id": "A", "checks": {}}), "checks")


class ScopeTests(unittest.TestCase):
    def test_fixture_cases(self) -> None:
        for case in FIXTURE["cases"]:
            with self.subTest(system=case["system"], includes=case["includes"]):
                chosen = select_scope(FIXTURE["rows"], FIXTURE["id_column"], case["system"], case["includes"])
                self.assertEqual([row[FIXTURE["id_column"]] for row in chosen], case["expected"])


class HashTests(unittest.TestCase):
    headers = ["ID", "Text", "Compliance"]
    rows = [{"ID": "R1", "Text": "One", "Compliance": "Not verified"}, {"ID": "R2", "Text": "Two", "Compliance": ""}]
    includes = ["Requirement", "System"]

    def hash(self, rows=None, headers=None, system=None, includes=None, status=False) -> str:
        return content_hash(
            headers or self.headers, self.rows if rows is None else rows, system,
            includes or self.includes, status, ["Compliance"],
        )

    def test_stable_and_prefixed(self) -> None:
        self.assertEqual(self.hash(), self.hash())
        self.assertRegex(self.hash(), r"^sha256:[0-9a-f]{64}$")

    def test_known_value(self) -> None:
        digest = content_hash(["ID"], [{"ID": "R1"}], None, ["Requirement"], False, [])
        self.assertEqual(digest, "sha256:" + __import__("hashlib").sha256(
            '["reqtable-baseline/1",{"system":null,"includes":["Requirement"],"status":false},["ID"],[["R1"]]]'.encode()
        ).hexdigest())

    def test_changes_with_a_cell(self) -> None:
        edited = [dict(self.rows[0], Text="One!"), self.rows[1]]
        self.assertNotEqual(self.hash(), self.hash(rows=edited))

    def test_line_endings_are_normalised(self) -> None:
        crlf = [dict(self.rows[0], Text="a\r\nb"), self.rows[1]]
        lf = [dict(self.rows[0], Text="a\nb"), self.rows[1]]
        self.assertEqual(self.hash(rows=crlf), self.hash(rows=lf))

    def test_status_column_only_counts_when_captured(self) -> None:
        progressed = [dict(self.rows[0], Compliance="Compliant"), self.rows[1]]
        self.assertEqual(self.hash(), self.hash(rows=progressed))
        self.assertNotEqual(self.hash(status=True), self.hash(rows=progressed, status=True))
        self.assertNotEqual(self.hash(), self.hash(status=True))

    def test_changes_with_scope(self) -> None:
        self.assertNotEqual(self.hash(), self.hash(system="SYS-A"))
        self.assertNotEqual(self.hash(), self.hash(includes=["Requirement", "System", "Test"]))
        self.assertNotEqual(self.hash(), self.hash(rows=self.rows[:1]))
        self.assertEqual(self.hash(includes=["System", "Requirement"]), self.hash())


def manifest(name: str, system: str | None = None, **extra: object) -> Manifest:
    parsed = BaselineName.parse(name)
    fields = dict(
        name=name, gate=parsed.gate, supersedes=None, system=system, includes=["Requirement", "System"],
        captures_status=False, status_columns=["Compliance"], content_hash="sha256:" + "0" * 64,
        source="requirements.csv", created="2026-01-01T00:00:00+00:00", created_by="t",
    )
    return Manifest(**{**fields, **extra})


class NamingTests(unittest.TestCase):
    def test_parse_and_format(self) -> None:
        self.assertEqual(BaselineName.parse("SRR"), BaselineName("SRR", None, None))
        self.assertEqual(BaselineName.parse("SRR-2"), BaselineName("SRR", 2, None))
        self.assertEqual(BaselineName.parse("DDR-2/SYS-REPORT"), BaselineName("DDR", 2, "SYS-REPORT"))
        self.assertEqual(str(BaselineName("SRR", 1)), "SRR")
        self.assertEqual(str(BaselineName("SRR", 3)), "SRR-3")
        self.assertEqual(str(BaselineName("DDR", 2, "SYS-A")), "DDR-2/SYS-A")
        self.assertEqual(str(BaselineName("DDR", 1, "SYS-A")), "DDR/SYS-A")
        self.assertEqual(str(BaselineName.parse("MY-GATE-3")), "MY-GATE-3")

    def test_next_name_numbers_each_base_separately(self) -> None:
        self.assertEqual(next_name([], "SRR", None), (BaselineName("SRR", 1), None))
        existing = [manifest("SRR"), manifest("SRR-2"), manifest("DDR/SYS-A", "SYS-A")]
        self.assertEqual(next_name(existing, "SRR", None), (BaselineName("SRR", 3), "SRR-2"))
        self.assertEqual(next_name(existing, "DDR", "SYS-A"), (BaselineName("DDR", 2, "SYS-A"), "DDR/SYS-A"))
        self.assertEqual(next_name(existing, "DDR", "SYS-B"), (BaselineName("DDR", 1, "SYS-B"), None))

    def test_resolve(self) -> None:
        all_ = [manifest("SRR"), manifest("SRR-2"), manifest("DDR/SYS-A", "SYS-A"), manifest("DDR-2/SYS-A", "SYS-A")]
        self.assertEqual(resolve("SRR", all_).name, "SRR-2")
        self.assertEqual(resolve("SRR-1", all_).name, "SRR")
        self.assertEqual(resolve("SRR-2", all_).name, "SRR-2")
        self.assertEqual(resolve("DDR/SYS-A", all_).name, "DDR-2/SYS-A")
        self.assertEqual(resolve("DDR-1/SYS-A", all_).name, "DDR/SYS-A")
        self.assertEqual(resolve("DDR-2/SYS-A", all_).name, "DDR-2/SYS-A")
        for missing in ("PDR", "SRR-3", "DDR", "DDR/SYS-B"):
            with self.subTest(missing), self.assertRaises(InputError) as caught:
                resolve(missing, all_)
            self.assertIn("SRR-2", str(caught.exception))

    def test_sort_follows_gate_order_then_number(self) -> None:
        config = {"gates": [{"id": "SRR"}, {"id": "PDR"}]}
        shuffled = [manifest("PDR"), manifest("SRR-2"), manifest("OTHER"), manifest("SRR")]
        self.assertEqual([m.name for m in sort_manifests(shuffled, config)], ["SRR", "SRR-2", "PDR", "OTHER"])

    def test_manifest_round_trip_and_validation(self) -> None:
        original = manifest("SRR-2", supersedes="SRR")
        self.assertEqual(Manifest.from_dict(json.loads(json.dumps(original.to_dict()))), original)
        self.assertEqual(list(original.to_dict())[:3], ["format", "name", "gate"])
        for broken in ({**original.to_dict(), "gate": "PDR"}, {**original.to_dict(), "includes": "x"}, {"name": "x"}):
            with self.subTest(broken), self.assertRaises(ValueError):
                Manifest.from_dict(broken)


CSV_TEXT = "ID,Type,Name,Part of,Allocated to,Verified by,Compliance\nSYS-A,System,Product,,,,\nR1,,,,SYS-A,,Not verified\n"
GIT_IDENT = ("-c", "user.name=Tester", "-c", "user.email=t@example.com")


def make_config(store: str, **changes: object) -> dict:
    config = copy.deepcopy(DEFAULT_CONFIG)
    config.update(id_column="ID", traceability=True, **changes)
    config["baselines"]["store"] = store
    return config


def quiet(messages: list[str]):
    return messages.append


class FileStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.input = self.root / "requirements.csv"
        self.input.write_text(CSV_TEXT, encoding="utf-8")
        self.config = make_config("files")
        self.warnings: list[str] = []
        self.store = open_store(self.input, self.config, lambda p: read_csv_table(str(p), self.config), self.warnings.append)

    def test_create_list_read(self) -> None:
        made = create_baseline(self.store, self.config, "SRR", None)
        folder = self.root / "baselines" / "SRR"
        self.assertEqual(sorted(p.name for p in folder.iterdir()), ["manifest.json", "requirements.csv", "source.csv"])
        self.assertEqual((folder / "source.csv").read_bytes(), self.input.read_bytes())
        raw = (folder / "requirements.csv").read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbfID,Type") and b"\r\n" in raw)
        self.assertEqual(made.source, "requirements.csv")
        self.assertIsNone(made.supersedes)
        self.assertEqual(self.store.list(), [made])
        table = self.store.read(made)
        self.assertEqual(table.headers, read_csv_table(str(self.input), self.config).headers)
        self.assertEqual(table.rows[1]["Compliance"], "Not verified")

    def test_never_overwrites_and_renumbers(self) -> None:
        first = create_baseline(self.store, self.config, "SRR", None)
        second = create_baseline(self.store, self.config, "SRR", None)
        self.assertEqual((second.name, second.supersedes), ("SRR-2", "SRR"))
        folder = self.root / "baselines" / "SRR"
        with self.assertRaises(InputError):
            self.store.write(first, self.store.current())
        self.assertTrue((folder / "manifest.json").exists())
        self.assertEqual([m.name for m in self.store.list()], ["SRR", "SRR-2"])

    def test_system_scope_uses_nested_folders(self) -> None:
        made = create_baseline(self.store, self.config, "DDR", "SYS-A")
        self.assertEqual(made.name, "DDR/SYS-A")
        self.assertTrue((self.root / "baselines" / "DDR" / "SYS-A" / "manifest.json").exists())
        again = create_baseline(self.store, self.config, "DDR", "SYS-A")
        self.assertEqual(again.name, "DDR-2/SYS-A")
        self.assertEqual({m.name for m in self.store.list()}, {"DDR-2/SYS-A", "DDR/SYS-A"})

    def test_gate_and_system_arguments_are_checked(self) -> None:
        for gate, system, error in (
            ("NOPE", None, ConfigError), ("SRR", "SYS-A", ConfigError), ("DDR", None, ConfigError),
            ("DDR", "R1", InputError), ("DDR", "SYS-Z", InputError),
        ):
            with self.subTest(gate=gate, system=system), self.assertRaises(error):
                create_baseline(self.store, self.config, gate, system)
        self.assertFalse((self.root / "baselines").exists())
        with self.assertRaises(ConfigError):
            create_baseline(self.store, {**self.config, "traceability": False}, "DDR", "SYS-A")

    def test_unreadable_manifests_are_skipped_with_a_warning(self) -> None:
        create_baseline(self.store, self.config, "SRR", None)
        bad = self.root / "baselines" / "BAD"
        bad.mkdir()
        (bad / "manifest.json").write_text("{not json", encoding="utf-8")
        self.assertEqual([m.name for m in self.store.list()], ["SRR"])
        self.assertEqual(len(self.warnings), 1)

    def test_directory_resolves_beside_the_input(self) -> None:
        self.config["baselines"]["files"]["directory"] = "frozen/gates"
        store = open_store(self.input, self.config, lambda p: read_csv_table(str(p), self.config))
        create_baseline(store, self.config, "SRR", None)
        self.assertTrue((self.root / "frozen" / "gates" / "SRR" / "manifest.json").exists())


@unittest.skipUnless(shutil.which("git"), "git is not on PATH")
class GitStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        self.folder = self.repo / "docs"
        self.folder.mkdir()
        self.input = self.folder / "requirements.csv"
        self.input.write_text(CSV_TEXT, encoding="utf-8")
        self.git("init", "-q")
        self.git("config", "user.name", "Tester")
        self.git("config", "user.email", "t@example.com")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "first")
        self.config = make_config("git")
        self.warnings: list[str] = []
        self.store = open_store(self.input, self.config, lambda p: read_csv_table(str(p), self.config), self.warnings.append)

    def git(self, *args: str) -> str:
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True, text=True).stdout

    def test_create_makes_an_annotated_tag_with_the_manifest(self) -> None:
        made = create_baseline(self.store, self.config, "SRR", None)
        self.assertEqual(made.source, "docs/requirements.csv")
        self.assertEqual(made.created_by, "Tester")
        self.assertEqual(self.git("cat-file", "-t", "baseline/SRR").strip(), "tag")
        message = self.git("tag", "-l", "--format=%(contents)", "baseline/SRR")
        self.assertTrue(message.startswith("ReqTable baseline SRR\n\n{"))
        self.assertEqual(json.loads(message.split("\n\n", 1)[1]), made.to_dict())
        self.assertEqual(self.git("rev-parse", "baseline/SRR^{commit}"), self.git("rev-parse", "HEAD"))

    def test_hash_comes_from_head_and_read_returns_the_tagged_content(self) -> None:
        made = create_baseline(self.store, self.config, "SRR", None)
        table = read_csv_table(str(self.input), self.config)
        expected = content_hash(
            table.headers, select_scope(table.rows, "ID", None, made.includes), None, made.includes, False,
            made.status_columns,
        )
        self.assertEqual(made.content_hash, expected)
        self.input.write_text(CSV_TEXT.replace("Not verified", "Compliant"), encoding="utf-8")
        self.git("commit", "-q", "-am", "progress")
        self.assertEqual(self.store.read(made).rows[1]["Compliance"], "Not verified")
        self.assertEqual([m.name for m in self.store.list()], ["SRR"])

    def test_refuses_dirty_staged_and_untracked_sources(self) -> None:
        self.input.write_text(CSV_TEXT + "R2,,,,,,\n", encoding="utf-8")
        with self.assertRaises(InputError) as caught:
            create_baseline(self.store, self.config, "SRR", None)
        self.assertIn("commit", str(caught.exception))
        self.git("add", "docs/requirements.csv")
        with self.assertRaises(InputError):
            create_baseline(self.store, self.config, "SRR", None)
        self.git("commit", "-q", "-m", "second")
        create_baseline(self.store, self.config, "SRR", None)
        other = self.folder / "other.csv"
        other.write_text(CSV_TEXT, encoding="utf-8")
        untracked = open_store(other, self.config, lambda p: read_csv_table(str(p), self.config))
        with self.assertRaises(InputError):
            create_baseline(untracked, self.config, "PDR", None)
        self.assertEqual(self.git("tag", "-l").split(), ["baseline/SRR"])

    def test_refuses_input_outside_a_work_tree(self) -> None:
        with tempfile.TemporaryDirectory() as outside:
            path = Path(outside) / "requirements.csv"
            path.write_text(CSV_TEXT, encoding="utf-8")
            env = {"GIT_CEILING_DIRECTORIES": str(Path(outside).parent)}
            with unittest.mock.patch.dict(os.environ, env):
                store = open_store(path, self.config, lambda p: read_csv_table(str(p), self.config))
                with self.assertRaises(InputError):
                    create_baseline(store, self.config, "SRR", None)

    def test_renumbers_and_scopes(self) -> None:
        create_baseline(self.store, self.config, "SRR", None)
        second = create_baseline(self.store, self.config, "SRR", None)
        scoped = create_baseline(self.store, self.config, "DDR", "SYS-A")
        self.assertEqual((second.name, second.supersedes, scoped.name), ("SRR-2", "SRR", "DDR/SYS-A"))
        self.assertEqual(self.git("tag", "-l").split(), ["baseline/DDR/SYS-A", "baseline/SRR", "baseline/SRR-2"])
        self.assertEqual({m.name for m in self.store.list()}, {"SRR", "SRR-2", "DDR/SYS-A"})

    def test_foreign_tags_are_ignored_with_a_warning(self) -> None:
        create_baseline(self.store, self.config, "SRR", None)
        self.git("tag", "baseline/light")
        self.git(*GIT_IDENT, "tag", "-a", "baseline/notes", "-m", "just words")
        self.assertEqual([m.name for m in self.store.list()], ["SRR"])
        self.assertEqual(len(self.warnings), 2)

    def test_custom_tag_prefix(self) -> None:
        self.config["baselines"]["git"]["tag_prefix"] = "gate/"
        store = open_store(self.input, self.config, lambda p: read_csv_table(str(p), self.config))
        create_baseline(store, self.config, "SRR", None)
        self.assertEqual(self.git("tag", "-l").split(), ["gate/SRR"])


if __name__ == "__main__":
    unittest.main()
