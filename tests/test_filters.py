import shutil
import subprocess
import unittest

from reqtable.html_report import FILTER_JS


@unittest.skipUnless(shutil.which("node"), "Node is needed to exercise the report's JavaScript")
class EmptyFilterTests(unittest.TestCase):
    def run_js(self, assertions):
        subprocess.run(["node"], input='const assert=require("node:assert/strict");\n'
                       + FILTER_JS + assertions, text=True, check=True)

    def test_empty_matches_blank_and_whitespace_only_cells(self):
        self.run_js("""
const only=new Set([EMPTY_FILTER]);
assert.equal(valueFilterMatches(only,""),true);
assert.equal(valueFilterMatches(only,"  \\n\\t"),true);
assert.equal(valueFilterMatches(only,undefined),true);
assert.equal(valueFilterMatches(only,"Must"),false);
""")

    def test_empty_combines_with_values_as_or(self):
        self.run_js("""
const both=new Set([EMPTY_FILTER,"Must"]);
assert.equal(valueFilterMatches(both,"Must"),true);
assert.equal(valueFilterMatches(both," "),true);
assert.equal(valueFilterMatches(both,"Should"),false);
const plain=new Set(["Must"]);
assert.equal(valueFilterMatches(plain,""),false);
assert.equal(valueFilterMatches(plain," "),false);
""")

    def test_options_list_blank_separately_and_label_reads_empty(self):
        self.run_js("""
const options=valueFilterOptions(["b","","a"," ","b","a10","a2"]);
assert.equal(options.blank,true);
assert.deepEqual(options.listed,["a","a2","a10","b"]);
assert.equal(valueFilterOptions(["x","y"]).blank,false);
assert.equal(valueFilterLabel(EMPTY_FILTER),"Empty");
assert.equal(valueFilterLabel("Must"),"“Must”");
""")


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(shutil.which("node"), "Node is needed to exercise the report's JavaScript")
class FilteredToEmptyTests(unittest.TestCase):
    def test_only_filters_that_hide_every_existing_row_count(self):
        subprocess.run(["node"], input='const assert=require("node:assert/strict");\n' + FILTER_JS + """
assert.equal(filteredToEmpty(1,0,5),true);
assert.equal(filteredToEmpty(0,0,5),false);
assert.equal(filteredToEmpty(2,3,5),false);
assert.equal(filteredToEmpty(1,0,0),false);
""", text=True, check=True)
