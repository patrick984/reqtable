"""Styles for the GUI page. Colours are tokens on :root so the dark scheme only redefines them."""

STYLE = r"""
:root {
  --bg: #f5f6f8; --surface: #ffffff; --surface-2: #eef0f4; --text: #1d2330; --muted: #5b6475;
  --line: #d9dde6; --accent: #2457d6; --accent-text: #ffffff; --accent-soft: #e3ebfd;
  --ok: #1a7f4b; --ok-soft: #e1f4ea; --bad: #b42318; --bad-soft: #fde8e6; --warn-soft: #fff4d6;
  --code-bg: #111827; --code-text: #e5e7eb; --radius: 10px;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #12151b; --surface: #1a1e27; --surface-2: #232834; --text: #e6e9ef; --muted: #9aa3b5;
    --line: #2f3645; --accent: #7aa2ff; --accent-text: #0c1020; --accent-soft: #212c4a;
    --ok: #5fd39a; --ok-soft: #173326; --bad: #ff8d82; --bad-soft: #3a1c1a; --warn-soft: #3b3217;
    --code-bg: #0b0e14; --code-text: #dfe3ec;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text); font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
a { color: var(--accent); }
.app { max-width: 1100px; margin: 0 auto; padding: 0 24px 48px; }
header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px 24px; flex-wrap: wrap; padding: 18px 0 8px; }
header h1 { margin: 0; font-size: 22px; }
header h1 a { color: inherit; text-decoration: none; }
header p { margin: 2px 0 0; color: var(--muted); max-width: 640px; }
main:focus { outline: none; }
main.wizard { max-width: 880px; margin: 0 auto; }
h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); margin: 0 0 10px; }
h2.pagetitle { font-size: 22px; text-transform: none; letter-spacing: 0; color: var(--text); margin: 0 0 4px; }
h2.pagetitle:focus { outline: none; }
h2.section { margin: 26px 0 12px; }
h3 { margin: 0; font-size: 16px; }
h3.group { margin: 18px 0 8px; font-size: 12px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); }
.card, a.tile { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); }
.card { padding: 18px; margin-bottom: 16px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; }
.jobs { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
a.tile { display: block; padding: 14px 16px; color: var(--text); text-decoration: none; }
a.tile:hover { border-color: var(--accent); }
a.tile .when { display: block; color: var(--muted); font-size: 13px; margin-top: 4px; }
a.tile.job { background: var(--accent-soft); border-color: transparent; }
a.tile.job:hover { border-color: var(--accent); }
a.tile.job .sum { display: block; color: var(--muted); font-size: 13px; margin: 4px 0 8px; }
a.tile.job ol { margin: 0; padding-left: 20px; font-size: 13px; }
.wizbar { display: flex; align-items: baseline; gap: 6px 16px; flex-wrap: wrap; margin: 8px 0 12px; }
.wizbar .task { font-weight: 600; }
.journeybar { background: var(--accent-soft); border-radius: var(--radius); padding: 10px 14px; margin-bottom: 12px; }
.journeybar p { margin: 0; }
.journeybar ol { list-style: none; display: flex; flex-wrap: wrap; gap: 4px 14px; margin: 6px 0 0; padding: 0; font-size: 13px; color: var(--muted); }
.journeybar li[aria-current="step"] { color: var(--text); font-weight: 600; }
.journeybar li.done::before { content: "\2713\00a0"; color: var(--ok); }
.stepper { list-style: none; display: flex; flex-wrap: wrap; gap: 6px 18px; margin: 4px 0 14px; padding: 0; font-size: 14px; }
.stepper li { display: flex; align-items: center; gap: 6px; color: var(--muted); }
.stepper .num { display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px; border-radius: 50%; border: 1px solid var(--line); font-size: 12px; background: var(--surface); }
.stepper li.done .num { background: var(--ok-soft); border-color: var(--ok); color: var(--ok); }
.stepper [aria-current="step"] { color: var(--text); font-weight: 700; }
.stepper [aria-current="step"] .num { background: var(--accent); border-color: var(--accent); color: var(--accent-text); }
.wizfoot { display: flex; align-items: center; justify-content: space-between; gap: 10px 16px; flex-wrap: wrap; margin: 4px 0 16px; }
.wizfoot .why { color: var(--muted); font-size: 13px; flex: 1; min-width: 160px; text-align: right; margin: 0; }
.wizfoot .go { display: flex; align-items: center; gap: 12px; flex: 1; justify-content: flex-end; flex-wrap: wrap; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }
.cards .opt { position: relative; display: block; margin: 0; padding: 12px 14px; border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); cursor: pointer; font-weight: 400; }
.cards .opt:hover { border-color: var(--accent); }
.cards .opt:has(input:checked) { border-color: var(--accent); background: var(--accent-soft); box-shadow: inset 0 0 0 1px var(--accent); }
.cards .opt:has(input:focus-visible) { outline: 3px solid var(--accent); outline-offset: 1px; }
.cards .opt input { position: absolute; opacity: 0; pointer-events: none; }
.cards .opt .opt-title { display: block; font-weight: 700; }
.cards .opt .opt-desc { display: block; color: var(--muted); font-size: 13px; margin-top: 2px; }
.cards.next .opt { background: var(--surface); }
.cards.next a.opt { color: var(--text); text-decoration: none; }
.cards.next button.opt { width: 100%; text-align: left; font: inherit; color: var(--text); }
.preview { margin-top: 8px; font-size: 13px; overflow-x: auto; }
.preview table, table.grid { border-collapse: collapse; width: 100%; font-size: 13px; }
.preview th, .preview td, table.grid th, table.grid td { border: 1px solid var(--line); padding: 3px 8px; text-align: left; max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.preview th, table.grid th { background: var(--surface-2); font-weight: 600; }
.preview .count { color: var(--muted); margin: 0 0 4px; } .preview .count strong { color: var(--text); }
.xscroll { overflow-x: auto; }
.check { display: flex; gap: 8px; align-items: baseline; margin: 2px 0; font-weight: 400; }
.check input { width: auto; }
.badge { display: inline-block; font-size: 11px; padding: 0 6px; border-radius: 99px; background: var(--surface-2); color: var(--muted); margin-left: 6px; }
.badge.strict { background: var(--warn-soft); color: var(--text); }
.waiver { display: grid; grid-template-columns: minmax(120px, 1fr) minmax(160px, 2fr) auto; gap: 6px; margin: 0 0 6px; }
ul.plain { margin: 6px 0 0; padding-left: 18px; font-size: 13px; }
.banner.soft { background: var(--warn-soft); }
.banner.fail { background: var(--bad-soft); white-space: pre-wrap; }
.waiveoffer { margin-top: 10px; }
.waiveoffer .actions { margin-top: 6px; }
.srcrow { border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; margin: 0 0 10px; background: var(--surface); }
.srcrow .top { display: grid; grid-template-columns: minmax(0, 1fr) minmax(160px, 220px) 120px; gap: 10px; align-items: end; }
.srcrow .nm { font-weight: 600; word-break: break-word; } .srcrow .sub { color: var(--muted); font-size: 12px; }
.srcrow label.mini { font-size: 12px; margin: 0 0 2px; color: var(--muted); font-weight: 500; }
table.cols { width: 100%; margin-top: 10px; border-collapse: collapse; font-size: 14px; }
table.cols th { text-align: left; font-size: 12px; color: var(--muted); font-weight: 500; padding: 2px 6px; }
table.cols td { padding: 3px 6px; vertical-align: middle; border-top: 1px solid var(--line); }
table.cols td.src { font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 13px; word-break: break-word; }
table.cols select, table.cols input { padding: 4px 6px; }
pre.json { margin: 0; padding: 12px 14px; background: var(--code-bg); color: var(--code-text); border-radius: 8px; overflow: auto; max-height: 340px; font: 12px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; user-select: all; }
.field { margin: 0 0 16px; } .field[hidden] { display: none; }
.field label { display: block; font-weight: 600; margin-bottom: 4px; }
.req { font-weight: 500; font-size: 12px; color: var(--accent); margin-left: 6px; }
.help { color: var(--muted); font-size: 13px; margin: 4px 0 0; }
.note { color: var(--muted); font-size: 13px; margin: 4px 0 0; }
input[type=text], input[type=number], select {
  width: 100%; padding: 8px 10px; font: inherit; color: var(--text); background: var(--surface);
  border: 1px solid var(--line); border-radius: 8px;
}
.pathrow { display: flex; gap: 8px; } .pathrow input { flex: 1; min-width: 0; }
button, a.btn { font: inherit; cursor: pointer; border-radius: 8px; border: 1px solid var(--line); background: var(--surface-2); color: var(--text); padding: 8px 14px; text-decoration: none; display: inline-block; }
button:hover:not(:disabled), a.btn:hover { border-color: var(--accent); }
button:disabled { opacity: .5; cursor: not-allowed; }
button.primary, a.btn.primary { background: var(--accent); color: var(--accent-text); border-color: var(--accent); font-weight: 600; }
button.small { padding: 3px 9px; font-size: 13px; }
:focus-visible { outline: 3px solid var(--accent); outline-offset: 1px; }
details.more { margin: 8px 0 16px; border-top: 1px solid var(--line); padding-top: 12px; }
details.more > summary { cursor: pointer; font-weight: 600; color: var(--accent); margin-bottom: 12px; }
.tabs { display: inline-flex; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }
.tabs button { border: 0; border-radius: 0; background: var(--surface); padding: 4px 12px; font-size: 13px; }
.tabs button[aria-pressed="true"] { background: var(--accent); color: var(--accent-text); }
.commandbar { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 8px; flex-wrap: wrap; }
pre.command, pre.output { margin: 0; padding: 12px 14px; background: var(--code-bg); color: var(--code-text); border-radius: 8px; overflow-x: auto; font: 13px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; white-space: pre; user-select: all; }
pre.output { user-select: text; max-height: 320px; overflow: auto; }
.hint { color: var(--muted); }
.actions { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 14px; }
.result { margin-top: 14px; }
.banner { padding: 12px 14px; border-radius: 8px; margin-bottom: 10px; }
.banner.ok { background: var(--ok-soft); } .banner.bad { background: var(--bad-soft); }
.banner strong { display: block; }
.banner .cli-error { display: block; margin-top: 6px; font: 600 14px ui-monospace, Menlo, Consolas, monospace; color: var(--bad); word-break: break-word; }
.banner.warn { background: var(--warn-soft); font-size: 14px; }
.steps { list-style: none; margin: 0 0 12px; padding: 0; }
.step { border: 1px solid var(--line); border-radius: 8px; padding: 10px; margin-bottom: 8px; background: var(--surface); }
.step .head { display: flex; align-items: center; gap: 6px; }
.step .head .name { flex: 1; font-weight: 600; min-width: 0; }
.step pre { margin: 8px 0 0; padding: 8px 10px; background: var(--code-bg); color: var(--code-text); border-radius: 6px; font: 12px/1.45 ui-monospace, Menlo, Consolas, monospace; overflow-x: auto; }
.empty { color: var(--muted); }
dialog { border: 1px solid var(--line); border-radius: var(--radius); background: var(--surface); color: var(--text); padding: 0; width: min(640px, 94vw); }
dialog::backdrop { background: rgba(0,0,0,.45); }
dialog#drawer { margin: 0 0 0 auto; height: 100vh; max-height: 100vh; width: min(460px, 100vw); border-radius: 0; border-width: 0 0 0 1px; }
.drawer-inner { padding: 16px; height: 100%; overflow: auto; }
.drawer-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 10px; }
.drawer-head h2 { margin: 0; }
.dlg { padding: 16px; display: flex; flex-direction: column; gap: 10px; max-height: 80vh; }
.dlg .where { font: 13px ui-monospace, Menlo, Consolas, monospace; word-break: break-all; color: var(--muted); }
.dlg .places { display: flex; gap: 6px; flex-wrap: wrap; }
.dlg ul { list-style: none; margin: 0; padding: 0; overflow: auto; border: 1px solid var(--line); border-radius: 8px; min-height: 120px; flex: 1; }
.dlg li button { display: block; width: 100%; text-align: left; border: 0; border-radius: 0; background: transparent; padding: 8px 12px; }
.dlg li button:hover { background: var(--accent-soft); }
.dlg .foot { display: flex; gap: 8px; justify-content: flex-end; flex-wrap: wrap; align-items: center; }
.dlg .foot input { flex: 1; min-width: 160px; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
@media (max-width: 760px) {
  .app { padding: 0 16px 40px; }
  .srcrow .top { grid-template-columns: minmax(0, 1fr); }
  .wizfoot .why { text-align: left; }
}
@media (max-width: 480px) {
  .waiver { grid-template-columns: minmax(0, 1fr); }
  .card { padding: 14px; }
}
"""
