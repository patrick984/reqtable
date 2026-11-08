from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from reqtable.baselines import Gate, content_hash, select_scope
from reqtable.core import DEFAULT_CONFIG, ConfigError, load_config, validate_config

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


if __name__ == "__main__":
    unittest.main()
