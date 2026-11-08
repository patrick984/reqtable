from __future__ import annotations

import copy
import json
import shutil
import subprocess
import unittest
from pathlib import Path

from reqtable.core import build_report_data, load_config, read_csv_table
from reqtable.findings import Finding, trace_findings
from reqtable.traceability import TRACE_MODEL_JS

UAT_CSV = Path(__file__).resolve().parent.parent / "requirements-uat.csv"


def uat_source() -> dict:
    config = load_config(None, {"id_column": "ID", "traceability": True})
    return build_report_data(read_csv_table(str(UAT_CSV), config), config, "uat.html")["source"]["new"]


def js_findings(cases: list[dict]) -> list[list[tuple]]:
    script = TRACE_MODEL_JS + "\nconst cases=" + json.dumps(cases) + r""";
console.log(JSON.stringify(cases.map(({rows,headers,idColumn})=>buildTraceIndex(rows,row=>String(row[idColumn]??"").trim(),
  {headers,idColumn}).issues.map(({id,field,message})=>[id,field,message]))));
"""
    output = subprocess.run(["node"], input=script, text=True, check=True, capture_output=True).stdout
    return [[tuple(finding) for finding in findings] for findings in json.loads(output)]


def py_findings(case: dict) -> list[tuple]:
    return [(f.id, f.field, f.message) for f in trace_findings(case["rows"], case["headers"], case["idColumn"])]


def case(name: str, rows: list[dict], headers: list[str] | None = None) -> dict:
    if headers is None:
        headers = list(dict.fromkeys(key for row in rows for key in row))
    return {"name": name, "rows": rows, "headers": headers, "idColumn": "ID"}


def term(ID, Name, Aliases="", **extra):
    return {"ID": ID, "Type": "Term", "Name": Name, "Aliases": Aliases, "Definition": "Definition", **extra}


def fixture_cases() -> list[dict]:
    """Rows from the JavaScript finding tests in test_traceability.py and test_values.py."""
    cases = [
        case("glossary matching and validation", [
            {"ID": "SYS", "Type": "System"}, {"ID": "SOURCE", "Type": "Source"}, {"ID": "NEED", "Type": "Need"},
            term("CSV", "Comma-Separated Values", "CSV; CSV", **{"Source refs": "SOURCE"}),
            term("CACHE", "Data Cache"), term("SHARED", "Shared Data Cache"),
            term("SINGLE", "Baseline", "", **{"Auto Link": "Yes"}),
            term("SKIP", "Report"), term("UTF", "Unicode Transformation Format", "UTF-8"),
            term("JOIN", "Proof of Concept"),
            term("CLASH1", "First Term", "CLASH; Shared Data Cache Format"),
            term("CLASH2", "Second Term", "CLASH; Shared Data Cache Format"),
            term("DUP1", "Duplicate Name"), term("DUP2", "duplicate name"),
            term("BLANK", "Blank Definition", "BD", Definition="  "),
            term("NAMELESS", "", "NM", **{"Source refs": "NEED"}),
        ]),
        case("canonical records", [
            {"ID": "SYS", "Type": "System"},
            {"ID": "A", "Type": "System", "Part of": "SYS"},
            {"ID": "B", "Type": "System", "Part of": "SYS"},
            {"ID": "N", "Type": "Need", "Source refs": "S"},
            {"ID": "S", "Type": "Source"},
            {"ID": "P", "Allocated to": " A; B ", "Owner": "SYS", "Source refs": "N"},
            {"ID": "C", "Derived from": "P"},
        ]),
        case("invalid imports", [
            {"ID": "SYS", "Type": "System", "Part of": "SUB"},
            {"ID": "SUB", "Type": "System", "Part of": "SYS"},
            {"ID": "P", "Allocated to": "SYS; absent; SYS; N", "Derived from": "C; P", "Origin": "Self-derived"},
            {"ID": "C", "Derived from": "P; NEW"},
            {"ID": "N", "Type": "Need"},
            {"ID": "X; Y", "Type": "Unknown"},
        ]),
        case("links resolve in both directions", [
            {"ID": "SYS", "Type": "System"},
            {"ID": "R1", "Type": "Requirement", "Verified by": "T1; T2"},
            {"ID": "T1", "Type": "Test", "Test plan": "TP"},
            {"ID": "T2", "Type": "Test"},
            {"ID": "TP", "Type": "Test plan"},
        ]),
        case("invalid test links", [
            {"ID": "SYS", "Type": "System"},
            {"ID": "R1", "Type": "Requirement", "Verified by": "TP; MISSING; R1; T1; T1"},
            {"ID": "T1", "Type": "Test", "Test plan": "TP; TP2", "Verified by": "T1"},
            {"ID": "TP", "Type": "Test plan"},
            {"ID": "TP2", "Type": "Test plan"},
            {"ID": "T2", "Type": "Test", "Test plan": "T1"},
            {"ID": "N", "Type": "Need", "Test plan": "TP"},
        ]),
        case("test plan links", [{"ID": "SYS", "Type": "System"}, {"ID": "T", "Type": "Test", "Test plan": "TP"},
                                 {"ID": "TP", "Type": "Test plan"}]),
        case("deleting a test", [
            {"ID": "R1", "Type": "Requirement", "Verified by": "T1; T2"},
            {"ID": "T1", "Type": "Test", "Test plan": "TP"},
            {"ID": "TP", "Type": "Test plan"},
        ]),
        case("verification method on tests", [
            {"ID": "V1", "Type": "Value", "Field": "Verification Method", "Name": "Automated test", "Definition": "Runs unattended."},
            {"ID": "T1", "Type": "Test", "Verification Method": "Automated test"},
            {"ID": "T2", "Type": "Test", "Verification Method": "Eyeball it"},
        ], ["ID", "Type", "Name", "Definition", "Verification Method", "Field", "Multiple", "Test plan", "Verified by"]),
    ]

    def level(ID, Name, Aliases=""):
        return {"ID": ID, "Type": "Value", "Field": "Level", "Name": Name, "Aliases": Aliases, "Definition": "A level."}

    cases.append(case("test coverage", [
        {"ID": "F1", "Type": "Field", "Name": "Level", "Multiple": "Yes", "Definition": "V-model level."},
        level("L-UNIT", "Unit", "Unit test"), level("L-SYS", "System"), level("L-ACC", "Acceptance", "UAT"),
        {"ID": "P1", "Type": "Value", "Field": "Priority", "Name": "Must", "Definition": "Required."},
        {"ID": "T-UNIT", "Type": "Test", "Level": "Unit test"}, {"ID": "T-SYS", "Type": "Test", "Level": "System"},
        {"ID": "T-NONE", "Type": "Test"},
        {"ID": "R-GAP", "Level": "Unit; System; UAT", "Priority": "Must", "Verified by": "T-UNIT"},
        {"ID": "R-OK", "Level": "Unit; System", "Verified by": "T-UNIT; T-SYS"},
        {"ID": "R-UNPLANNED", "Verified by": "T-UNIT"},
        {"ID": "R-UNLEVELLED-TEST", "Level": "System", "Verified by": "T-NONE"},
        {"ID": "R-UNLINKED", "Level": "System"},
    ], ["ID", "Type", "Name", "Field", "Multiple", "Aliases", "Definition", "Level", "Priority", "Verified by"]))

    def state(Field, Name, Aliases=""):
        return {"ID": f"V-{Field}-{Name}", "Type": "Value", "Field": Field, "Name": Name, "Aliases": Aliases, "Definition": "Defined."}

    def test(ID, Result):
        return {"ID": ID, "Type": "Test", "Result": Result}

    verification_headers = ["ID", "Type", "Name", "Field", "Aliases", "Definition", "Compliance", "Result", "Verified by"]
    verification_values = [state("Compliance", "Compliant"), state("Compliance", "Non-compliant"),
                           state("Result", "Passed", "Pass"), state("Result", "Failed")]
    cases += [
        case("compliant needs passed tests", [*verification_values,
            test("T-PASS", "Passed"), test("T-ALIAS", "Pass"), test("T-FAIL", "Failed"), test("T-BLANK", ""), test("T-BLANK2", ""),
            {"ID": "R-OK", "Compliance": "Compliant", "Verified by": "T-PASS; T-ALIAS"},
            {"ID": "R-FAILED", "Compliance": "Compliant", "Verified by": "T-PASS; T-FAIL"},
            {"ID": "R-TWO", "Compliance": "Compliant", "Verified by": "T-FAIL; T-BLANK"},
            {"ID": "R-THREE", "Compliance": "Compliant", "Verified by": "T-FAIL; T-BLANK; T-PASS; T-BLANK2"},
            {"ID": "R-NO-TESTS", "Compliance": "Compliant"},
            {"ID": "R-NON", "Compliance": "Non-compliant", "Verified by": "T-FAIL"},
            {"ID": "R-BLANK-COMPLIANCE", "Verified by": "T-FAIL"},
        ], verification_headers),
        case("compliant without values", [test("T", "Failed"), {"ID": "R", "Compliance": "Compliant", "Verified by": "T"}],
             verification_headers),
        case("compliance and result record types", [*verification_values,
            {"ID": "R", "Compliance": "Compliant", "Result": "Passed"},
            {"ID": "T", "Type": "Test", "Compliance": "Compliant", "Result": "Passed"},
            {"ID": "N", "Type": "Need", "Result": "Failed"},
            {"ID": "S", "Type": "System", "Compliance": " "},
        ], verification_headers),
    ]

    matrix_headers = ["ID", "Type", "Name", "Field", "Aliases", "Multiple", "Definition", "Requirement", "Verification Method",
                      "Verification Level", "Compliance", "Result", "Verified by"]
    matrix_values = [
        {"ID": "F-Verification Method", "Type": "Field", "Name": "Verification Method", "Multiple": "Yes", "Definition": "Field."},
        {"ID": "F-Verification Level", "Type": "Field", "Name": "Verification Level", "Multiple": "Yes", "Definition": "Field."},
        state("Verification Method", "Inspection"), state("Verification Method", "Test", "Try it"),
        state("Verification Level", "Unit"), state("Verification Level", "Acceptance", "UAT"),
        state("Compliance", "Not verified"), state("Compliance", "Compliant"), state("Result", "Passed", "Pass"),
    ]
    for name, rows, with_values in [
        ("matrix aliases", [{"ID": "R1", "Requirement": "Text", "Verification Method": "Try it; Inspection",
                             "Verification Level": "UAT; Unit"}, {"ID": "R2", "Name": "Named", "Requirement": "Text"}], True),
        ("matrix extras", [{"ID": "R1", "Verification Method": "Test; Telepathy", "Verification Level": "Beta"}], True),
        ("matrix tests", [{"ID": "T1", "Type": "Test", "Name": "Core test", "Result": "Pass"}, {"ID": "T2", "Type": "Test"},
                          {"ID": "R1", "Compliance": "Compliant", "Verified by": "T1; T2"},
                          {"ID": "R2", "Compliance": "Not verified"}, {"ID": "R3", "Compliance": "Not verified"}, {"ID": "R4"}], True),
        ("matrix without values", [{"ID": "R1", "Verification Method": "Test"}], False),
        ("matrix csv", [{"ID": "T1", "Type": "Test", "Result": "Passed"}, {"ID": "T2", "Type": "Test"},
                        {"ID": "R1", "Requirement": "Shall work", "Verification Method": "Test; Telepathy", "Verification Level": "Unit",
                         "Compliance": "Compliant", "Verified by": "T1; T2"}], True),
    ]:
        cases.append(case(name, [*matrix_values, *rows] if with_values else rows, matrix_headers))

    value_headers = ["ID", "Type", "Name", "Definition", "Aliases", "Priority", "Method", "Field", "Multiple", "Part of", "Source refs"]

    def value(ID, Field, Name, **extra):
        return {"ID": ID, "Type": "Value", "Field": Field, "Name": Name, "Definition": "Defined.", **extra}

    def field(ID, Name, Multiple="", **extra):
        return {"ID": ID, "Type": "Field", "Name": Name, "Definition": "Describes.", "Multiple": Multiple, **extra}

    def req(ID, **extra):
        return {"ID": ID, "Type": "Requirement", **extra}

    base = [value("V1", "Priority", "Must"), value("V2", "Priority", "Should"),
            value("M1", "Method", "Manual browser test", Aliases="Manual verification; Browser check"),
            value("M2", "Method", "Automated test"), field("F2", "Method", "yes")]
    for name, rows in [
        ("values clean", [*base, req("R1", Priority="Must", Method="Manual browser test; Automated test"),
                          req("R2", Priority=" Should "), req("R3")]),
        ("values loose", [value("V1", "Priority", "Must"), req("R1", Method="Anything goes")]),
        ("values base", base),
        ("values spellings", [*base, req("R1", Priority="Shoud"), req("R2", Priority="must"),
                              req("R3", Method="Manual verification"), req("R4", Priority="Must; Should"),
                              req("R5", Method="automated TEST"), {"ID": "N", "Type": "Need", "Priority": "Urgent"}]),
        ("values multiple", [*base, req("R1", Method="Automated test; Browser check; Bogus;; "),
                             req("R2", Method="Automated test; automated test")]),
        ("invalid value records", [
            value("V1", "Priority", "Must"), value("DUP", "Priority", "must"),
            value("A1", "Method", "One", Aliases="Uno"), value("A2", "Method", "Two", Aliases="uno; One"),
            {"ID": "NOFIELD", "Type": "Value", "Name": "Orphan", "Definition": "Defined."},
            value("GHOST", "Colour", "Red"), value("RES1", "Type", "System"), value("RES2", "ID", "X"),
            value("RES3", "Part of", "SYS"), value("RES4", "Multiple", "Yes"),
            value("NONAME", "Priority", ""), value("NODEF", "Priority", "Could", Definition=" "),
            value("LINK", "Priority", "Won't", **{"Source refs": "SYS"})]),
        ("ghost value only", [value("GHOST", "Colour", "Red")]),
        ("invalid field records", [
            value("V1", "Priority", "Must"), field("F1", "Priority"), field("F2", "Priority", "Yes"),
            field("NONAME", ""), field("GHOST", "Colour"), field("RES", "Type"),
            field("BAD", "Method", "Maybe"), field("NODEF", "Source refs", "", Definition=""),
            field("DOC", "Part of"), field("UNUSED", "Definition", "No"), field("LINK", "Aliases", "", **{"Part of": "SYS"})]),
        ("field rule", [value("V1", "Priority", "Must"), field("F1", "Priority", "Yes")]),
    ]:
        cases.append(case(name, [{"ID": "SYS", "Type": "System"}, *rows], value_headers))
    return cases


def mutated(source: dict, name: str, edits: dict[str, dict[str, str]]) -> dict:
    rows = copy.deepcopy(source["rows"])
    by_id = {row["ID"]: row for row in rows}
    for row_id, cells in edits.items():
        by_id[row_id].update(cells)
    return {**case(name, rows, source["headers"])}


MUTATIONS = {
    "missing Allocated to target": {"REQ-005": {"Allocated to": "SYS-NOPE"}},
    "wrong target type": {"REQ-005": {"Allocated to": "REQ-004"}},
    "duplicate reference": {"REQ-005": {"Source refs": "SRC-BASELINE; SRC-BASELINE"}},
    "self link": {"REQ-004": {"Derived from": "REQ-004"}},
    "single link with two targets": {"REQ-005": {"Owner": "SYS-REVIEW; SYS-GRID"}},
    "link that does not apply": {"SYS-GRID": {"Allocated to": "SYS-REPORT"}},
    "semicolon in ID": {"REQ-005": {"ID": "REQ-005; X"}},
    "two roots": {"SYS-GENERATOR": {"Part of": ""}},
    "Part of cycle": {"SYS-REQTABLE": {"Part of": "SYS-TRACE"}},
    "Derived from cycle": {"REQ-003": {"Derived from": "REQ-247"}},
    "unknown type": {"REQ-005": {"Type": "Requirment"}},
    "undefined Verification Level": {"REQ-005": {"Verification Level": "Subsystem"}},
    "one value allowed": {"REQ-005": {"Priority": "Must; Should"}},
    "alias spelling": {"REQ-005": {"Verification Level": "Unit test"}},
    "case-only spelling": {"REQ-005": {"Priority": "must"}},
    "duplicate in Multiple cell": {"REQ-142": {"Verification Level": "Unit; unit"}},
    "Compliant with a failed test": {"TEST-CORE": {"Result": "Failed"}, "REQ-018": {"Compliance": "Compliant"}},
    "Compliant with an unrun test": {"REQ-253": {"Compliance": "Compliant"}},
    "Result on a requirement": {"REQ-005": {"Result": "Passed"}},
    "Compliance on a test": {"TEST-CORE": {"Compliance": "Compliant"}},
    "coverage gap": {"REQ-018": {"Verification Level": "Unit; System"}},
    "Value record for a missing column": {"VAL-PRIORITY-COULD": {"Field": "Colour"}},
    "Value record without a name": {"VAL-PRIORITY-COULD": {"Name": ""}},
    "duplicate Value name": {"VAL-PRIORITY-COULD": {"Name": "MUST"}},
    "clashing Value alias": {"VAL-RESULT-FAILED": {"Aliases": "pass"}},
    "Field record with bad Multiple": {"FIELD-PRIORITY": {"Multiple": "Maybe"}},
    "Field record for a reserved column": {"FIELD-PRIORITY": {"Name": "Owner"}},
    "two Field records for one column": {"FIELD-EXECUTION": {"Name": "Priority"}},
    "glossary term without a definition": {"TERM-UAT": {"Definition": ""}},
    "shared glossary spelling": {"TERM-HTML": {"Aliases": "CSV"}},
    "duplicate glossary name": {"TERM-HTML": {"Name": "comma-separated values"}},
    "self-derived requirement without rationale": {"REQ-005": {"Origin": "Self-derived", "Rationale": ""}},
}


@unittest.skipUnless(shutil.which("node"), "Node is needed to run the report's JavaScript")
class FindingParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = uat_source()

    def assert_parity(self, cases: list[dict]) -> list[list[tuple]]:
        expected = js_findings(cases)
        for item, js in zip(cases, expected, strict=True):
            with self.subTest(item["name"]):
                self.assertEqual(py_findings(item), js)
        return expected

    def test_shipped_uat_csv_has_no_findings(self):
        item = case("uat", self.source["rows"], self.source["headers"])
        self.assertEqual(self.assert_parity([item]), [[]])
        self.assertEqual(trace_findings(item["rows"], item["headers"], "ID"), [])

    def test_fixture_tables(self):
        found = self.assert_parity(fixture_cases())
        self.assertGreater(sum(map(len, found)), 50)

    def test_targeted_mutations(self):
        cases = [mutated(self.source, name, edits) for name, edits in MUTATIONS.items()]
        for item, findings in zip(cases, self.assert_parity(cases)):
            self.assertTrue(findings, item["name"])

    def test_findings_are_frozen_values(self):
        self.assertEqual(Finding(None, "Part of", "x"), Finding(None, "Part of", "x"))
        with self.assertRaises(AttributeError):
            Finding("R", "Type", "x").id = "S"


if __name__ == "__main__":
    unittest.main()
