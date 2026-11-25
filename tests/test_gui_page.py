from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from reqtable.gui_page import render_page


def script_of(page: str) -> str:
    found = re.search(r"<script>(.*)</script>", page, re.S)
    assert found is not None
    return found.group(1)


class PageTests(unittest.TestCase):
    def test_the_token_is_embedded_and_no_placeholder_is_left(self) -> None:
        page = render_page("abc-123")
        self.assertIn('const TOKEN = "abc-123";', page)
        self.assertNotRegex(page, r"__[A-Z]+__")

    def test_the_page_is_a_home_grid_and_a_wizard_not_three_columns(self) -> None:
        page = render_page("t")
        for gone in ('class="layout"', 'id="nav"', "renderNav", "renderIntro"):
            self.assertNotIn(gone, page)
        for route in ("#/task/", "#/journey/", "hashchange"):
            self.assertIn(route, page)

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_the_script_is_valid_javascript(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "page.js"
            path.write_text(script_of(render_page("t")), encoding="utf-8")
            done = subprocess.run(
                ["node", "--check", str(path)], capture_output=True, text=True
            )
        self.assertEqual(done.returncode, 0, done.stderr)


if __name__ == "__main__":
    unittest.main()
