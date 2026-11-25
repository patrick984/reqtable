"""The single page the GUI serves. It renders every form from /api/workflows, so field lists live only in reqtable.gui."""

from __future__ import annotations

import json

from .gui_page_core import CORE_JS
from .gui_page_drawer import DRAWER_JS
from .gui_page_form import FORM_JS
from .gui_page_gates import GATES_JS
from .gui_page_mapping import MAPPING_JS
from .gui_page_run import RUN_JS
from .gui_page_style import STYLE
from .gui_page_wizard import WIZARD_JS

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>reqtable</title>
<style>__STYLE__</style>
</head>
<body>
<div class="app">
<header>
  <div>
    <h1><a href="#/">reqtable</a></h1>
    <p>Turn requirements spreadsheets into reports. Every step shows the exact command it runs, so you can repeat it later.</p>
  </div>
  <button type="button" id="wfopen" aria-haspopup="dialog">Your workflow (0)</button>
</header>
<main id="main" tabindex="-1"></main>
</div>
<dialog id="picker" aria-label="Choose a file or folder"></dialog>
<dialog id="drawer" aria-labelledby="drawer-title">
  <div class="drawer-inner">
    <div class="drawer-head"><h2 id="drawer-title">Your workflow</h2><button type="button" id="drawer-close">Close</button></div>
    <div id="drawer-body"></div>
  </div>
</dialog>
<div class="sr" role="status" aria-live="polite" id="live"></div>
<script>
__SCRIPT__
start();
</script>
</body>
</html>
"""

SCRIPT = "".join((CORE_JS, FORM_JS, GATES_JS, RUN_JS, DRAWER_JS, MAPPING_JS, WIZARD_JS))


def render_page(token: str) -> str:
    return PAGE.replace("__STYLE__", STYLE).replace(
        "__SCRIPT__", SCRIPT.replace("__TOKEN__", json.dumps(token))
    )
