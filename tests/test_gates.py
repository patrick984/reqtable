from __future__ import annotations

import json
import unittest
from pathlib import Path

from reqtable.core import (
    DEFAULT_CONFIG,
    ConfigError,
    resolve_gate_enforcement,
    validate_gates,
)
from reqtable.gates import evaluate_check, evaluate_gate, format_result

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "gate_checks.json").read_text(
        encoding="utf-8"
    )
)


def check_with(**extra):
    return {"id": "c", "description": "d", **extra}


def gate_with(*checks):
    return [{"id": "G", "checks": list(checks)}]


class SharedCaseTests(unittest.TestCase):
    def test_fixture_cases(self) -> None:
        for index, case in enumerate(FIXTURE["cases"]):
            with self.subTest(index=index, check=case["check"]):
                result = evaluate_check(
                    {"id": "x", "description": "x", **case["check"]},
                    FIXTURE["rows"],
                    FIXTURE["headers"],
                    FIXTURE["id_column"],
                    case.get("system"),
                    [],
                )
                if "error" in case:
                    self.assertEqual(result["error"], case["error"])
                    self.assertNotIn("total", result)
                else:
                    self.assertIsNone(result["error"])
                    self.assertEqual(
                        (result["total"], result["failing"]),
                        (case["total"], case["failing"]),
                    )


class NoFindingsTests(unittest.TestCase):
    check = {"id": "n", "description": "n", "no_findings": True}

    def run_check(self, findings, **extra):
        return evaluate_check(
            {**self.check, **extra},
            FIXTURE["rows"],
            FIXTURE["headers"],
            "ID",
            None,
            findings,
        )

    def test_clean(self) -> None:
        result = self.run_check([])
        self.assertEqual((result["total"], result["failing"]), (8, []))

    def test_record_findings_fail_in_table_order(self) -> None:
        result = self.run_check(
            [("R3", "x", "m"), ("R1", "x", "m"), ("R1", "y", "m"), ("NOPE", "x", "m")]
        )
        self.assertEqual(result["failing"], ["R1", "R3"])

    def test_global_finding_is_a_pseudo_entry(self) -> None:
        result = self.run_check([(None, "", "Cycle in Part of")])
        self.assertEqual(
            (result["total"], result["failing"], result["global"]),
            (9, [""], ["Cycle in Part of"]),
        )

    def test_scoped_findings_ignore_out_of_scope_records(self) -> None:
        result = evaluate_check(
            self.check,
            FIXTURE["rows"],
            FIXTURE["headers"],
            "ID",
            "SYS-B",
            [("R3", "x", "m")],
        )
        self.assertEqual(result["failing"], [])

    def test_applies_to_narrows_records(self) -> None:
        result = self.run_check([("T2", "x", "m")], applies_to={"type": "Requirement"})
        self.assertEqual((result["total"], result["failing"]), (3, []))


class UnchangedSinceTests(unittest.TestCase):
    check = {"id": "u", "description": "u", "unchanged_since": True}
    controls = {
        "baselines": [],
        "records": {
            "R1": {"row": {}},
            "R3": {"row": {}},
            "GONE": {"row": {"ID": "GONE", "Allocated to": "SYS-B"}},
            "GONE2": {"row": {"ID": "GONE2", "Allocated to": "SYS-A"}},
        },
    }

    def run_check(self, findings, system=None, controls=controls, **extra):
        return evaluate_check(
            {**self.check, **extra},
            FIXTURE["rows"],
            FIXTURE["headers"],
            "ID",
            system,
            findings,
            controls,
        )

    def test_counts_removed_ids_as_records(self) -> None:
        result = self.run_check([])
        self.assertEqual(
            (result["total"], result["failing"], result["global"]), (10, [], [])
        )

    def test_fails_change_findings_in_finding_order_once(self) -> None:
        findings = [
            ("GONE", "ID", "Removed since PDR without an approved change request."),
            (
                "R3",
                "Priority",
                "Changed since PDR (Priority) without an approved change request.",
            ),
            ("R1", "x", "Target R9 is missing."),
            (
                "R3",
                "Priority",
                "Changed since PDR (Priority) without an approved change request.",
            ),
            ("NOPE", "ID", "Removed since PDR without an approved change request."),
        ]
        self.assertEqual(self.run_check(findings)["failing"], ["GONE", "R3"])

    def test_system_scope_keeps_only_removals_from_its_subtree(self) -> None:
        findings = [
            (
                "R3",
                "Priority",
                "Changed since PDR (Priority) without an approved change request.",
            ),
            ("GONE", "ID", "Removed since PDR without an approved change request."),
            ("GONE2", "ID", "Removed since PDR without an approved change request."),
        ]
        scoped = self.run_check(findings, "SYS-B")
        everything = self.run_check([])
        self.assertEqual(scoped["failing"], ["GONE"])
        self.assertLess(scoped["total"], everything["total"])

    def test_without_controls_passes(self) -> None:
        result = self.run_check([], controls=None)
        self.assertEqual((result["total"], result["failing"]), (8, []))

    def test_applies_to_narrows_records(self) -> None:
        findings = [("T2", "ID", "Added since TRR without an approved change request.")]
        self.assertEqual(
            self.run_check(findings, applies_to={"type": "Requirement"})["failing"], []
        )
        self.assertEqual(self.run_check(findings)["failing"], ["T2"])


class EnforcementTests(unittest.TestCase):
    gate = {
        "id": "G",
        "name": "Gate",
        "checks": [
            check_with(id="a", filled="Priority"),
            check_with(id="b", filled="Priority", enforcement="advisory"),
            check_with(id="c", filled="Priority", enforcement="strict"),
            check_with(id="ok", filled="Requirement", enforcement="strict"),
        ],
    }

    def levels(self, gate, default):
        return {
            check["id"]: check["enforcement"]
            for check in resolve_gate_enforcement(gate, default)["checks"]
        }

    def test_effective_level_is_check_then_gate_then_default(self) -> None:
        self.assertEqual(
            self.levels(self.gate, "advisory"),
            {"a": "advisory", "b": "advisory", "c": "strict", "ok": "strict"},
        )
        self.assertEqual(
            self.levels(self.gate, "strict"),
            {"a": "strict", "b": "advisory", "c": "strict", "ok": "strict"},
        )
        gate = {**self.gate, "enforcement": "strict"}
        self.assertEqual(
            self.levels(gate, "advisory"),
            {"a": "strict", "b": "advisory", "c": "strict", "ok": "strict"},
        )
        self.assertEqual(
            self.levels({**self.gate, "enforcement": "advisory"}, "strict")["a"],
            "advisory",
        )

    def evaluate(self, gate):
        return evaluate_gate(gate, FIXTURE["rows"], FIXTURE["headers"], "ID", None, [])

    def test_only_failing_strict_checks_block(self) -> None:
        result = self.evaluate(resolve_gate_enforcement(self.gate, "advisory"))
        self.assertEqual(
            (result["ready"], result["blocking"], result["blocked"]),
            (False, ["c"], True),
        )
        self.assertEqual(
            [check["enforcement"] for check in result["checks"]],
            ["advisory", "advisory", "strict", "strict"],
        )

    def test_failing_advisory_checks_do_not_block(self) -> None:
        result = self.evaluate(
            resolve_gate_enforcement(
                {**self.gate, "checks": self.gate["checks"][:2]}, "advisory"
            )
        )
        self.assertEqual(
            (result["ready"], result["blocking"], result["blocked"]), (False, [], False)
        )

    def test_a_strict_check_that_errors_blocks(self) -> None:
        result = self.evaluate(
            resolve_gate_enforcement(
                {"id": "G", "checks": [check_with(filled="Owner")]}, "strict"
            )
        )
        self.assertEqual((result["blocking"], result["blocked"]), (["c"], True))

    def test_format_marks_strict_failures_and_blocked(self) -> None:
        lines = format_result(
            self.evaluate(resolve_gate_enforcement(self.gate, "advisory"))
        )
        self.assertEqual(lines[0], "G Gate: not ready, blocked")
        self.assertEqual(lines[1][:24], "  FAIL (advisory) a  d: ")
        self.assertTrue(lines[3].startswith("  FAIL (strict) c  d: "))
        self.assertEqual(lines[4], "  pass ok  d")


class GateTests(unittest.TestCase):
    def test_ready_needs_no_failures_and_no_errors(self) -> None:
        run = lambda *checks: evaluate_gate(
            {"id": "G", "name": "Gate", "checks": list(checks)},
            FIXTURE["rows"],
            FIXTURE["headers"],
            "ID",
            None,
            [],
        )
        good = check_with(filled="Requirement")
        self.assertTrue(run(good)["ready"])
        self.assertFalse(run(good, check_with(id="b", filled="Priority"))["ready"])
        self.assertFalse(run(good, check_with(id="e", filled="Owner"))["ready"])

    def test_format(self) -> None:
        result = evaluate_gate(
            {
                "id": "G",
                "name": "Gate",
                "checks": [
                    check_with(id="a", filled="Priority"),
                    check_with(id="b", filled="Requirement"),
                    check_with(id="c", filled="Owner"),
                ],
            },
            FIXTURE["rows"],
            FIXTURE["headers"],
            "ID",
            "SYS-A",
            [],
        )
        self.assertFalse(result["blocked"])
        self.assertEqual(
            format_result(result),
            [
                "G Gate for SYS-A: not ready",
                "  FAIL (advisory) a  d: 1 of 2 records: R2",
                "  pass b  d",
                "  ERROR (advisory) c  The table has no “Owner” column.",
            ],
        )


class ValidationTests(unittest.TestCase):
    def reject(self, fragment, *checks):
        with self.assertRaises(ConfigError) as caught:
            validate_gates(gate_with(*checks))
        self.assertIn(fragment, str(caught.exception))
        self.assertIn("G", str(caught.exception))

    def test_preset_is_valid_with_unique_ids(self) -> None:
        validate_gates(DEFAULT_CONFIG["gates"])
        ids = [
            check["id"] for gate in DEFAULT_CONFIG["gates"] for check in gate["checks"]
        ]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 31)
        change = {
            gate["id"]: [c for c in gate["checks"] if "unchanged_since" in c]
            for gate in DEFAULT_CONFIG["gates"]
        }
        self.assertEqual(change.pop("SRR"), [])
        for gate_id, checks in change.items():
            self.assertEqual(
                checks,
                [
                    {
                        "id": f"{gate_id.lower()}-change-control",
                        "description": "Every change since the last baseline has an approved change request",
                        "unchanged_since": True,
                    }
                ],
            )

    def test_rejections(self) -> None:
        self.reject("needs exactly one condition", check_with())
        self.reject("needs exactly one condition", check_with(filled="A", linked="B"))
        self.reject("unknown configuration key", check_with(filled="A", bogus=1))
        self.reject("'leaf'", check_with(filled="A", leaf=True))
        self.reject("'leaf'", check_with(linked="A", leaf="yes"))
        self.reject("one column", check_with(**{"in": {"A": "x"}}))
        self.reject("one column", check_with(**{"in": {"A": ["x"], "B": ["y"]}}))
        self.reject("must be true", check_with(no_findings=False))
        self.reject("must name a column", check_with(filled=""))
        self.reject("non-empty string", check_with(description=""))
        self.reject(
            "duplicate check ID", check_with(filled="A"), check_with(filled="B")
        )
        self.reject(
            "unknown record type", check_with(filled="A", applies_to={"type": "Nope"})
        )
        self.reject(
            "applies_to.Priority", check_with(filled="A", applies_to={"Priority": 3})
        )

    def test_unchanged_since_must_be_true(self) -> None:
        validate_gates(gate_with(check_with(unchanged_since=True)))
        self.reject("must be true", check_with(unchanged_since="SRR"))

    def test_signoffs_complete_is_an_unknown_key(self) -> None:
        self.reject("unknown configuration key", check_with(signoffs_complete=True))

    def test_signoff_roles_are_validated(self) -> None:
        validate_gates([{"id": "G", "signoff": [{"role": "Reviewer", "min": 1}]}])
        for roles in (
            {},
            [{"role": "A"}],
            [{"role": "A", "min": 0}],
            [{"role": "A", "min": True}],
            [{"role": "", "min": 1}],
            [{"role": "A", "min": 1, "x": 1}],
            [{"role": "A", "min": 1}, {"role": "a", "min": 2}],
            ["A"],
        ):
            with self.assertRaises(ConfigError, msg=roles):
                validate_gates([{"id": "G", "signoff": roles}])


if __name__ == "__main__":
    unittest.main()
