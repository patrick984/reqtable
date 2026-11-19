# Systems and traceability pilot

Build the pilot from ReqTable's own requirements CSV.

```sh
python -m reqtable requirements-uat.csv --id-column ID --traceability \
  --document-mode develop -o requirements-uat-develop.html
python -m reqtable requirements-uat.csv --id-column ID --traceability \
  -o requirements-uat.html
```

To refresh both pilot reports and `examples/requirements-diff.html` in one step, run `python3 build_reports.py` from anywhere. Each report embeds its generation time, so a rerun changes that line even when nothing else changed.

The report opens in **Requirements** with the core writing columns, including Verification Method. The view buttons form three groups with a divider between them. **Define** holds Needs & sources, Requirements and Systems. **Verify** holds Tests, Verification, Gates and Change requests. **Reference** holds Glossary and All fields. Use **Columns** to show more writing fields such as Rationale, or **All fields** to see every CSV record and relationship column. The **System** selector includes all requirements, unallocated requirements, and individual systems. After you choose a system, select **Include subsystems** for a combined view. A requirement shared across systems, such as `REQ-003`, appears once in that view. The controls to the right of the view buttons change with the view and show only what applies to it, wrapping onto their own row when the window is narrow.

Select a record and use **Links** in the workspace bar, **View → Links**, or, in Develop mode, **Links** in a cell's right-click menu to open the Links panel for that record and see or add relationships. A dot in the ID cell marks records that already have links. Following a link opens the corresponding record view, and **Back to previous record** steps back through the browser history, the same as the browser's Back button. If a target is filtered out within the current grid, **Reveal in grid** shows it alongside that view. The active-filters menu can remove the exception or the system filter. **Trace findings** in the same panel reports invalid links and cycles, and the ⚑ flag in a cell opens a popover with that cell's findings. **Show in Links** in the popover opens the panel at those findings. An optional **Name** gives a requirement a short label in link lists and pickers. You can edit it in **All fields**.

The browser's Back and Forward buttons step through your views, Grid and Matrix layouts, system scope and record jumps. Selecting another row updates the current step without adding one. The address after `#` reopens the report at that place, for example `report.html#view=verification&mode=matrix&system=SYS-REPORT&record=REQ-003`. Copy it to share a view or bookmark it. This also works for reports opened from disk. Reports shown inside another page do not change that page's history.

In Develop mode, use **Systems** to add subsystems, rename them, move them, and delete them. The delete dialog shows affected subsystems, allocations, and owners and lets you choose how to handle each group. Use **Needs & sources** to add needs and citations. From a requirement's **Links** panel, use **Allocate to…** to select multiple systems or **Add child requirement…** to create a new row with its parent link filled in. **Rename ID…** updates incoming links and comments, and Undo restores a deletion and its links together.

Enable the pilot with `--traceability` or `"traceability": true` in the JSON configuration. The generator adds missing traceability columns. A blank `Type` means `Requirement`, and multi-value link fields use semicolon-separated IDs. Use the same flag when regenerating from a saved CSV. With the default JSON comments format, the exported comments return as annotations. See the [traceability proposal](design/requirements-traceability-proposal.md) for the schema and model.
