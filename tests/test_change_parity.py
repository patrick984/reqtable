from __future__ import annotations

import copy
import json
import random
import shutil
import subprocess
import unittest
from pathlib import Path

from reqtable.comparison import COMPARISON_JS
from reqtable.findings import trace_findings
from reqtable.traceability import TRACE_MODEL_JS

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "change_control.json").read_text(
        encoding="utf-8"
    )
)
TOKENS = [
    "",
    " ",
    "R1",
    "R3",
    "R6",
    "R7",
    "SYS-A",
    "SYS-B",
    "Approved",
    "Implemented",
    "Rejected",
    "Change request",
    "System",
    "Must",
    "x",
    "R1; R7",
    "Not verified",
    "Compliant",
    "Need",
]
DATES = [
    "2026-01-01T00:00:00+00:00",
    "2026-02-01T00:00:00+00:00",
    "2026-03-01T00:00:00+00:00",
]


def mutated_cases(count: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    cases = []
    for _ in range(count):
        rows, controls = (
            copy.deepcopy(FIXTURE["rows"]),
            copy.deepcopy(FIXTURE["controls"]),
        )
        for _ in range(rng.randint(1, 5)):
            pick = rng.random()
            if pick < 0.6:
                rng.choice(rows)[rng.choice(FIXTURE["headers"])] = rng.choice(TOKENS)
            elif pick < 0.75 and len(rows) > 1:
                rows.pop(rng.randrange(len(rows)))
            elif pick < 0.85:
                rows.insert(rng.randrange(len(rows) + 1), dict(rng.choice(rows)))
            elif pick < 0.95:
                rng.choice(controls["baselines"])["created"] = rng.choice(DATES)
            else:
                rng.choice(controls["baselines"])["capturesStatus"] = True
        cases.append({"rows": rows, "controls": controls})
    return cases


@unittest.skipUnless(
    shutil.which("node"), "Node is needed to run the report's findings"
)
class ChangeControlParityTests(unittest.TestCase):
    def test_python_and_report_agree_on_mutated_change_control_tables(self) -> None:
        cases = mutated_cases(400, 20261108)
        script = (
            TRACE_MODEL_JS
            + "\n"
            + COMPARISON_JS
            + "\nconst cases="
            + json.dumps(cases)
            + ";\n"
            + (
                "console.log(JSON.stringify(cases.map(({rows,controls})=>buildTraceIndex(rows,"
                'row=>String(row.ID??"").trim(),{headers:'
                + json.dumps(FIXTURE["headers"])
                + ',idColumn:"ID",controls})'
                ".issues.map(({id,field,message})=>[id,field,message]))));"
            )
        )
        expected = json.loads(
            subprocess.run(
                ["node"], input=script, text=True, capture_output=True, check=True
            ).stdout
        )
        self.assertGreater(sum(map(len, expected)), len(cases))
        for index, (case, js) in enumerate(zip(cases, expected)):
            got = [
                [f.id, f.field, f.message]
                for f in trace_findings(
                    case["rows"], FIXTURE["headers"], "ID", case["controls"]
                )
            ]
            with self.subTest(case=index):
                self.assertEqual(got, js)


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(
    shutil.which("node"), "Node is needed to run the report's gate checks"
)
class ScopedRemovalTests(unittest.TestCase):
    def test_a_system_gate_counts_only_removals_from_its_own_subtree(self) -> None:
        from reqtable.gate_checks import GATE_CHECKS_JS
        from reqtable.gates import evaluate_check

        rows = [row for row in FIXTURE["rows"] if row["ID"] != "R1"]
        check = {"id": "c", "description": "d", "unchanged_since": True}
        findings = [
            (f.id, f.field, f.message)
            for f in trace_findings(rows, FIXTURE["headers"], "ID", FIXTURE["controls"])
        ]
        python = evaluate_check(
            check,
            rows,
            FIXTURE["headers"],
            "ID",
            "SYS-B",
            findings,
            FIXTURE["controls"],
        )
        script = (
            TRACE_MODEL_JS
            + "\n"
            + COMPARISON_JS
            + "\n"
            + GATE_CHECKS_JS
            + "\nconst rows="
            + json.dumps(rows)
            + ";\n"
            + (
                "const controls="
                + json.dumps(FIXTURE["controls"])
                + ",headers="
                + json.dumps(FIXTURE["headers"])
                + ";\n"
                'const issues=buildTraceIndex(rows,row=>String(row.ID??"").trim(),{headers,idColumn:"ID",controls}).issues;\n'
                "console.log(JSON.stringify(evaluateGateCheck("
                + json.dumps(check)
                + ',rows,"ID",headers,"SYS-B",issues,controls)));'
            )
        )
        report = json.loads(
            subprocess.run(
                ["node"], input=script, text=True, capture_output=True, check=True
            ).stdout
        )
        self.assertEqual(python["failing"], ["R5"])
        self.assertEqual(python["total"], 6)
        self.assertEqual(report["failing"], python["failing"])
        self.assertEqual(report["total"], python["total"])
