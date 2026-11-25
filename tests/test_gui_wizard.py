from __future__ import annotations

import unittest

from reqtable.gui import WORKFLOWS, WORKFLOWS_BY_ID, workflow_named
from reqtable.gui_wizard import JOURNEYS, NEXT, wizard_pages

FORM_WORKFLOWS = [w for w in WORKFLOWS if w.panel == "form"]


def page_ids(workflow_id: str) -> list[str]:
    return [page.id for page in wizard_pages(workflow_named(workflow_id))]


def field_page(workflow_id: str, name: str) -> str:
    return next(
        page.id
        for page in wizard_pages(workflow_named(workflow_id))
        if name in page.fields
    )


class WizardPageTests(unittest.TestCase):
    def test_every_field_is_on_exactly_one_page_in_registry_order(self) -> None:
        for workflow in FORM_WORKFLOWS:
            names = [f.name for f in workflow.fields]
            pages = wizard_pages(workflow)
            placed = [name for page in pages for name in page.fields]
            self.assertCountEqual(placed, names, workflow.id)
            for page in pages:
                self.assertEqual(
                    list(page.fields),
                    [n for n in names if n in page.fields],
                    f"{workflow.id}.{page.id}",
                )
                self.assertTrue(page.fields, f"{workflow.id}.{page.id}")
            self.assertEqual(len({page.id for page in pages}), len(pages), workflow.id)

    def test_pages_have_plain_titles_and_help(self) -> None:
        for workflow in WORKFLOWS:
            for page in wizard_pages(workflow):
                self.assertTrue(page.title and page.help.endswith("."), workflow.id)

    def test_files_come_first_and_hold_the_table_choices_with_their_file(self) -> None:
        for workflow in FORM_WORKFLOWS:
            self.assertEqual(wizard_pages(workflow)[0].id, "files", workflow.id)
        for name in ("input", "table", "sheet", "header_row", "id_column", "config"):
            self.assertEqual(field_page("create_baseline", name), "files", name)
        self.assertEqual(field_page("diff", "old"), "files")
        self.assertEqual(field_page("diff", "new"), "files")
        self.assertEqual(field_page("comments", "report"), "files")
        self.assertEqual(field_page("import_decisions", "package"), "files")

    def test_output_and_report_options_follow_on_an_options_page(self) -> None:
        self.assertEqual(page_ids("report"), ["files", "options"])
        self.assertEqual(field_page("report", "output"), "options")
        self.assertEqual(field_page("report", "document_mode"), "options")
        self.assertEqual(field_page("report", "encoding"), "options")
        self.assertEqual(page_ids("list_tables"), ["files"])

    def test_gate_fields_get_a_page_named_for_what_it_is(self) -> None:
        titles = {
            w.id: {p.id: p.title for p in wizard_pages(w)} for w in FORM_WORKFLOWS
        }
        self.assertEqual(titles["check_gate"]["gate"], "Gate")
        self.assertEqual(titles["sign_off"]["gate"], "Baseline and decision")
        self.assertEqual(titles["verify_baseline"]["gate"], "Baseline")
        for name in ("gate", "system", "waivers"):
            self.assertEqual(field_page("create_baseline", name), "gate")
        for name in ("baseline", "role", "decision"):
            self.assertEqual(field_page("sign_off", name), "gate")

    def test_a_page_of_only_advanced_fields_joins_the_page_before_it(self) -> None:
        self.assertEqual(page_ids("check_gate"), ["files", "gate"])
        self.assertEqual(field_page("check_gate", "encoding"), "gate")
        self.assertEqual(page_ids("list_baselines"), ["files"])
        self.assertEqual(page_ids("sign_off"), ["files", "gate", "options"])
        for workflow in FORM_WORKFLOWS:
            pages = wizard_pages(workflow)
            if len(pages) > 1 and pages[-1].id == "options":
                fields = {f.name: f for f in workflow.fields}
                self.assertFalse(all(fields[n].advanced for n in pages[-1].fields))

    def test_the_mapping_builder_has_its_own_four_pages(self) -> None:
        self.assertEqual(page_ids("mapping"), ["workbook", "tables", "save", "report"])
        self.assertEqual(wizard_pages(workflow_named("mapping"))[0].fields, ("input",))


class NextStepTests(unittest.TestCase):
    def test_every_step_names_real_workflows_and_fields_of_compatible_kinds(
        self,
    ) -> None:
        compatible = {"open", "save"}
        for source_id, steps in NEXT.items():
            source = workflow_named(source_id)
            for step in steps:
                target = workflow_named(step.workflow)
                self.assertNotEqual(source.id, target.id)
                self.assertTrue(step.label and step.why, step.workflow)
                self.assertTrue(step.carry, f"{source_id}->{step.workflow}")
                targets = [to for _, to in step.carry]
                self.assertEqual(len(targets), len(set(targets)))
                for frm, to in step.carry:
                    a = next(f for f in source.fields if f.name == frm)
                    b = next(f for f in target.fields if f.name == to)
                    self.assertTrue(
                        a.kind == b.kind or {a.kind, b.kind} <= compatible,
                        f"{source_id}.{frm} -> {step.workflow}.{to}",
                    )

    def test_the_documented_follow_ups_exist(self) -> None:
        def after(workflow_id: str) -> set[str]:
            return {s.workflow for s in NEXT.get(workflow_id, ())}

        self.assertEqual(after("report"), {"comments"})
        self.assertEqual(after("diff"), {"comments"})
        self.assertEqual(after("list_tables"), {"mapping", "report", "to_csv"})
        self.assertEqual(after("to_csv"), {"report", "diff"})
        self.assertEqual(after("create_baseline"), {"gate_package", "sign_off"})
        self.assertIn(("output", "package"), NEXT["gate_package"][0].carry)

    def test_tasks_that_only_look_have_no_follow_up(self) -> None:
        self.assertNotIn("list_baselines", NEXT)
        self.assertNotIn("verify_baseline", NEXT)


class JourneyTests(unittest.TestCase):
    def test_journeys_use_real_tasks_and_unique_ids(self) -> None:
        self.assertEqual(len({j.id for j in JOURNEYS}), len(JOURNEYS))
        for journey in JOURNEYS:
            self.assertTrue(journey.title and journey.summary.endswith("."))
            self.assertTrue(journey.steps)
            for step in journey.steps:
                self.assertIn(step.workflow, WORKFLOWS_BY_ID)
                self.assertTrue(step.why.endswith("."))

    def test_each_consecutive_pair_is_a_known_follow_up(self) -> None:
        for journey in JOURNEYS:
            for a, b in zip(journey.steps, journey.steps[1:]):
                self.assertIn(
                    b.workflow,
                    [s.workflow for s in NEXT.get(a.workflow, ())],
                    f"{journey.id}: {a.workflow} -> {b.workflow}",
                )

    def test_the_typical_jobs_are_there(self) -> None:
        by_title = {j.title: [s.workflow for s in j.steps] for j in JOURNEYS}
        self.assertEqual(
            by_title["Share requirements for review"], ["report", "comments"]
        )
        self.assertEqual(by_title["Edit requirements in the browser"], ["develop"])
        self.assertEqual(
            by_title["Hold a gate review"],
            [
                "check_gate",
                "create_baseline",
                "gate_package",
                "import_decisions",
                "verify_baseline",
            ],
        )


if __name__ == "__main__":
    unittest.main()
