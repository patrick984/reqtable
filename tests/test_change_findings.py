from __future__ import annotations

import json
import unittest
from pathlib import Path

from reqtable.findings import trace_findings

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "change_control.json").read_text(encoding="utf-8"))
CHANGE_MESSAGE = " without an approved change request."


def findings(rows=None, controls=None):
    rows = FIXTURE["rows"] if rows is None else rows
    return [(f.id, f.field, f.message) for f in trace_findings(rows, FIXTURE["headers"], "ID", controls)]


def row(**cells):
    return {header: cells.get(header, "") for header in FIXTURE["headers"]}


class ChangeFindingTests(unittest.TestCase):
    def test_fixture(self) -> None:
        found = [finding for finding in findings(controls=FIXTURE["controls"]) if finding[2].endswith(CHANGE_MESSAGE)]
        self.assertEqual(found, [tuple(item) for item in FIXTURE["expected"]])

    def test_change_findings_follow_the_others_and_are_marked(self) -> None:
        found = trace_findings(FIXTURE["rows"], FIXTURE["headers"], "ID", FIXTURE["controls"])
        plain = [f for f in trace_findings(FIXTURE["rows"], FIXTURE["headers"], "ID") if f.message != "Target R3 is missing."]
        self.assertEqual(found[:len(plain)], plain)
        self.assertEqual([f.message for f in found[len(plain):]], [item[2] for item in FIXTURE["expected"]])

    def test_without_controls_removed_affects_target_is_missing(self) -> None:
        self.assertIn(("CR3", "Affects", "Target R3 is missing."), findings())
        self.assertNotIn(("CR3", "Affects", "Target R3 is missing."), findings(controls=FIXTURE["controls"]))

    def test_affects_still_checks_unknown_targets(self) -> None:
        rows = [*FIXTURE["rows"], row(ID="CR9", Type="Change request", Affects="NOPE", **{"Change status": "Proposed"})]
        self.assertIn(("CR9", "Affects", "Target NOPE is missing."), findings(rows, FIXTURE["controls"]))

    def test_affects_applies_only_to_change_requests(self) -> None:
        rows = [*FIXTURE["rows"], row(ID="R8", **{"Allocated to": "SYS-A", "Affects": "R1"})]
        self.assertIn(("R8", "Affects", "Affects does not apply to Requirement records."), findings(rows))

    def test_change_status_applies_to_change_requests(self) -> None:
        rows = [*FIXTURE["rows"], row(ID="R8", **{"Allocated to": "SYS-A", "Change status": "Approved"})]
        self.assertIn(("R8", "Change status", "Change status applies to change requests."), findings(rows))

    def test_change_status_resolves_through_value_aliases(self) -> None:
        headers = [*FIXTURE["headers"], "Field", "Definition", "Aliases"]
        values = [
            {**row(ID=f"V{n}", Type="Value", Name=name), "Field": "Change status", "Definition": "d", "Aliases": alias}
            for n, (name, alias) in enumerate([("Proposed", ""), ("Approved", "OK"), ("Rejected", ""), ("Implemented", "")])
        ]
        rows = [{**r, "Change status": "OK" if r["ID"] == "CR2" else r["Change status"]} for r in FIXTURE["rows"]] + values
        found = [f.id for f in trace_findings(rows, headers, "ID", FIXTURE["controls"]) if f.message.endswith(CHANGE_MESSAGE)]
        self.assertNotIn("R6", found)

    def test_changed_lists_columns_in_header_order(self) -> None:
        rows = [{**r, "Priority": "Could", "Requirement": "R two, again"} if r["ID"] == "R2" else r for r in FIXTURE["rows"]]
        self.assertIn(
            ("R2", "Requirement", "Changed since PDR (Requirement, Priority) without an approved change request."),
            findings(rows, FIXTURE["controls"]),
        )

    def test_status_columns_count_when_the_baseline_captures_status(self) -> None:
        controls = {**FIXTURE["controls"], "baselines": [{**b, "capturesStatus": True} for b in FIXTURE["controls"]["baselines"]]}
        self.assertIn(
            ("R4", "Compliance", "Changed since PDR (Compliance) without an approved change request."),
            findings(controls=controls),
        )

    def test_rejected_change_request_does_not_authorise(self) -> None:
        rows = [{**r, "Change status": "Rejected"} if r["ID"] == "CR1" else r for r in FIXTURE["rows"]]
        self.assertIn(
            ("R1", "Requirement", "Changed since DDR/SYS-B (Requirement) without an approved change request."),
            findings(rows, FIXTURE["controls"]),
        )

    def test_tied_creation_attributes_additions_to_the_first_listed(self) -> None:
        baselines = [{**b, "created": "2026-01-01T00:00:00+00:00"} for b in FIXTURE["controls"]["baselines"]]
        self.assertIn(
            ("R5", "ID", "Added since PDR without an approved change request."),
            findings(controls={**FIXTURE["controls"], "baselines": baselines}),
        )

    def test_uncontrolled_record_is_not_added(self) -> None:
        rows = [*FIXTURE["rows"], row(ID="N1", Type="Need", Name="n")]
        self.assertNotIn("N1", [f[0] for f in findings(rows, FIXTURE["controls"]) if f[2].endswith(CHANGE_MESSAGE)])
