from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .baselines import (
    BaselineStore, build_controls, create_baseline, current_user, find_gate, load_baselines, open_store, require_scope_args,
    require_system_record, run_git, sort_manifests,
)
from .core import (
    DEFAULT_CONFIG,
    ConfigError,
    CsvSource,
    CsvTable,
    InputError,
    OutputError,
    ReqtableError,
    atomic_write_text,
    build_report_data,
    prepare_trace_table,
    resolve_gate_enforcement,
    extract_comments_csv,
    generation_time,
    load_config,
    read_csv_source,
)
from .gates import evaluate_gate, format_result, table_findings
from .html_report import render_report
from .review import build_package, import_decisions, sign_off, verify_baseline
from .waivers import describe_failure, plan_waivers, split_ids
from .xlsx import XlsxSelection, block_to_csv, describe, is_xlsx, mapping_template, read_mapped, read_selection


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Generate an offline requirements table or diff report.")
    result.add_argument("input", nargs="?", help="CSV or .xlsx input for snapshot mode")
    result.add_argument("--old", help="old/baseline CSV or .xlsx for diff mode, or git:REV[:PATH] to read a CSV from a git revision")
    result.add_argument("--new", help="new/current CSV or .xlsx for diff mode")
    result.add_argument("--extract-comments", metavar="REPORT.html", help="extract comments from a generated report")
    result.add_argument("-o", "--output", help="output HTML path, or CSV path to export an .xlsx input")
    result.add_argument("-c", "--config", help="JSON configuration path")
    result.add_argument("--id-column")
    result.add_argument("--title")
    result.add_argument("--document-mode", choices=("review", "develop"))
    result.add_argument(
        "--traceability", action=argparse.BooleanOptionalAction, default=None,
        help="interpret the CSV as a systems and traceability document",
    )
    result.add_argument("--encoding")
    result.add_argument("--delimiter")
    result.add_argument("--initial-diff-view", choices=("unified", "side-by-side"))
    result.add_argument("--changes-only", action="store_true", default=None)
    result.add_argument("--include-unchanged", action=argparse.BooleanOptionalAction, default=None)
    result.add_argument("--reviewer-initials")
    result.add_argument("--comments-column", default=None)
    result.add_argument("--comments-format", choices=("json", "text"), default=None)
    result.add_argument("--csv-base", choices=("new", "old", "union"), default="new")
    result.add_argument("--allow-comment-loss", action="store_true")
    result.add_argument("--table", help="read this table from each .xlsx input")
    result.add_argument("--sheet", help="read this sheet from each .xlsx input")
    result.add_argument("--header-row", type=int, metavar="N", help="header row number on --sheet; default is the first non-empty row")
    result.add_argument("--list-tables", metavar="WORKBOOK.xlsx", help="list the sheets and tables of a workbook and exit")
    result.add_argument(
        "--xlsx-mapping-template", metavar="WORKBOOK.xlsx",
        help="print a JSON configuration that maps every table and sheet of a workbook, and exit",
    )
    result.add_argument("--create-baseline", metavar="GATE", help="freeze the input as a baseline for this review gate, and exit")
    result.add_argument("--system", metavar="ID", help="System ID for --create-baseline or --check-gate on a system-scoped gate")
    result.add_argument(
        "--waive", metavar="CHECK_ID", action="append", default=[],
        help="with --create-baseline, waive this failing strict check (repeat, or comma-separate); needs --reason",
    )
    result.add_argument("--reason", help="why the --waive checks are waived; recorded in the baseline")
    result.add_argument("--list-baselines", action="store_true", help="list the baselines of the input (or --new), and exit")
    result.add_argument(
        "--baselines", metavar="NAME[,NAME...]",
        help="embed these gate baselines in the report so it can compare against them",
    )
    result.add_argument(
        "--check-gate", metavar="GATE",
        help="evaluate this review gate's readiness checks on the input; exit 0 when ready, 1 when not",
    )
    result.add_argument(
        "--sign-off", metavar="BASELINE",
        help="record a decision on this gate baseline (needs --role and --decision), and exit",
    )
    result.add_argument("--role", help="sign-off role for --sign-off, one of the gate's roles")
    result.add_argument("--decision", help="sign-off decision for --sign-off: Reviewed, Changes requested, Approved or Rejected")
    result.add_argument("--user", help="who made the decision for --sign-off, or who waives for --waive; default is git user.name or the login name")
    result.add_argument("--note", default="", help="free-text note for --sign-off")
    result.add_argument("--evidence", metavar="PATH", help="file that backs the decision for --sign-off, such as a signed PDF")
    result.add_argument(
        "--verify-baseline", metavar="BASELINE",
        help="recheck a baseline's content hash and sign-offs; exit 0 when intact and approved, 1 otherwise",
    )
    result.add_argument(
        "--gate-package", metavar="BASELINE",
        help="write the review package for a gate baseline to -o OUT.html, and exit",
    )
    result.add_argument(
        "--import-decisions", metavar="PACKAGE.html",
        help="record the decisions saved in a gate package copy as sign-offs, and exit",
    )
    result.add_argument("--print-default-config", action="store_true")
    result.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return result


def _overrides(args: argparse.Namespace) -> dict[str, object]:
    return {
        "id_column": args.id_column,
        "title": args.title,
        "document_mode": args.document_mode,
        "traceability": args.traceability,
        "csv.encoding": args.encoding,
        "csv.delimiter": args.delimiter,
        "diff.initial_view": args.initial_diff_view,
        "diff.initial_changes_only": args.changes_only,
        "diff.include_unchanged": args.include_unchanged,
        "comments.reviewer_initials": args.reviewer_initials,
        "comments.csv_column": args.comments_column,
        "comments.csv_format": args.comments_format,
    }


def git_source(spec: str, default_path: str, config: dict[str, object]) -> CsvSource:
    """Resolve git:REV[:PATH]; PATH defaults to the --new file's path."""
    rev, _, given = spec[len("git:"):].partition(":")
    if not rev:
        raise ConfigError("--old git: needs a revision, as git:REV or git:REV:PATH")
    path = Path(given or default_path)
    try:
        # --filters applies the repo's eol/attribute rules, as for a checked-out file.
        blob = run_git(path.parent, "cat-file", "--filters", f"{rev}:./{path.name}")
        short = run_git(path.parent, "rev-parse", "--short", f"{rev}^{{commit}}").decode().strip()
    except InputError as exc:
        raise InputError(f"cannot read {path} at {rev}: {exc}") from exc
    encoding = config["csv"]["encoding"]  # type: ignore[index]
    label = f"{path.name} @ {rev}" if rev.startswith(short) else f"{path.name} @ {rev} ({short})"
    try:
        return CsvSource(label, blob.decode(encoding), path)
    except (UnicodeError, LookupError) as exc:
        raise InputError(f"{label}: cannot decode as {encoding}: {exc}") from exc


def file_source(path: str) -> CsvSource:
    return CsvSource(str(Path(path)), None, Path(path))


def xlsx_source(path: str, selection: XlsxSelection, config: dict[str, object]) -> CsvSource:
    sources = config["xlsx"]["sources"]  # type: ignore[index]
    if sources:
        block = read_mapped(path, sources, config["id_column"], config["traceability"])  # type: ignore[arg-type]
    else:
        block = read_selection(path, selection)
    text = block_to_csv(block.rows, config["csv"]["delimiter"])  # type: ignore[index]
    # Name only: the label ends up in the report, which gets shared.
    return CsvSource(f"{Path(path).name} [{block.name}]", text, Path(path))


def input_source(path: str, selection: XlsxSelection, config: dict[str, object]) -> CsvSource:
    return xlsx_source(path, selection, config) if is_xlsx(path) else file_source(path)


def table_store(path: str, selection: XlsxSelection, config: dict[str, object]) -> BaselineStore:
    return open_store(path, config, lambda found: read_csv_source(input_source(str(found), selection, config), config))


def run_baseline_command(args: argparse.Namespace, selection: XlsxSelection, config: dict[str, object]) -> int:
    if args.create_baseline and args.list_baselines:
        raise ConfigError("--create-baseline and --list-baselines cannot be combined")
    if args.old or args.extract_comments or args.baselines or (args.create_baseline and args.new):
        raise ConfigError("--create-baseline and --list-baselines cannot be combined with diff options, --baselines or --extract-comments")
    if args.input and args.new:
        raise ConfigError("give the input as a positional argument or as --new, not both")
    path = args.input or (args.new if args.list_baselines else None)
    if not path:
        raise ConfigError("--create-baseline and --list-baselines need an input CSV or .xlsx")
    store = table_store(path, selection, config)
    if args.list_baselines:
        manifests = sort_manifests(store.list(), config)
        for manifest in manifests:
            digest = manifest.content_hash.removeprefix("sha256:")[:12]
            print("\t".join((manifest.name, manifest.gate, manifest.system or "-", manifest.created, manifest.created_by, digest)))
        if not manifests:
            print("No baselines.")
        return 0
    result = evaluate_input(store.current(), store, config, args.create_baseline, args.system)
    ids = split_ids(args.waive)
    user = args.user or current_user(store.input_path.resolve().parent)
    waivers = plan_waivers(result, ids, args.reason, user, generation_time())
    waived = set(ids)
    for check in result["checks"]:  # type: ignore[attr-defined]
        if check["error"] is None and not check["failing"] or check["id"] in waived:
            continue
        if check["enforcement"] == "strict":
            continue
        print(f"warning: {describe_failure(check)}", file=sys.stderr)
    blocked = [check for check in result["checks"] if check["id"] in result["blocking"] and check["id"] not in waived]  # type: ignore[attr-defined,index]
    if blocked:
        for check in blocked:
            print(f"blocked: {describe_failure(check)}", file=sys.stderr)
        hint = ", ".join(f"--waive {check['id']}" for check in blocked)
        print(f'Fix the data, or record a waiver: {hint} --reason "..."', file=sys.stderr)
        return 1
    made = create_baseline(store, config, args.create_baseline, args.system, waivers)
    for waiver in waivers:
        print(f"Waived {waiver.check} ({len(waiver.failing)} records): {waiver.reason}")
    print(f"Created baseline {made.name} ({made.content_hash}) {store.where(made)}")
    return 0


REVIEW_FLAGS = ("sign_off", "verify_baseline", "gate_package", "import_decisions")


def run_review_command(args: argparse.Namespace, selection: XlsxSelection, config: dict[str, object]) -> int:
    if not args.input:
        raise ConfigError("--sign-off, --verify-baseline, --gate-package and --import-decisions need an input CSV or .xlsx")
    store = table_store(args.input, selection, config)
    if args.sign_off:
        if not args.role or not args.decision:
            raise ConfigError("--sign-off needs --role and --decision")
        print(sign_off(store, config, args.sign_off, args.role, args.decision, args.user, args.note, args.evidence))
        return 0
    if args.gate_package:
        if not args.output:
            raise ConfigError("--gate-package needs --output")
        data = build_package(store, config, args.gate_package, Path(args.output).name)
        for warning in data["meta"].get("warnings", []):
            print(f"warning: {warning}", file=sys.stderr)
        atomic_write_text(args.output, render_report(data))
        print(f"Wrote {data['package']['baseline']['name']} gate package to {args.output}")
        return 0
    if args.import_decisions:
        print("\n".join(import_decisions(store, config, args.import_decisions)))
        return 0
    lines, approved = verify_baseline(store, config, args.verify_baseline)
    print("\n".join(lines))
    return 0 if approved else 1


def evaluate_input(
    table: CsvTable, store: BaselineStore, config: dict[str, object], gate_id: str, system: str | None
) -> dict[str, object]:
    gate = find_gate(config, gate_id)
    require_scope_args(gate, system, config)
    if config["traceability"]:
        table, _ = prepare_trace_table(table, config)
    require_system_record(table, system)
    controls = build_controls(store, config)
    findings = table_findings(table.rows, table.headers, config["id_column"], controls)  # type: ignore[arg-type]
    configured = next(entry for entry in config["gates"] if entry["id"] == gate.id)  # type: ignore[attr-defined]
    resolved = resolve_gate_enforcement(configured, config["baselines"]["enforcement"])  # type: ignore[index]
    return evaluate_gate(resolved, table.rows, table.headers, config["id_column"], system, findings, controls)  # type: ignore[arg-type]


def run_check_gate(args: argparse.Namespace, selection: XlsxSelection, config: dict[str, object]) -> int:
    if args.create_baseline or args.list_baselines or args.baselines or args.old or args.new or args.extract_comments:
        raise ConfigError(
            "--check-gate cannot be combined with --create-baseline, --list-baselines, --baselines, --old, --new or --extract-comments"
        )
    if not args.input:
        raise ConfigError("--check-gate needs an input CSV or .xlsx")
    table = read_csv_source(input_source(args.input, selection, config), config)
    result = evaluate_input(table, table_store(args.input, selection, config), config, args.check_gate, args.system)
    print("\n".join(format_result(result)))
    return 0 if result["ready"] else 1


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.print_default_config:
        print(json.dumps(DEFAULT_CONFIG, indent=2))
        return 0
    if args.list_tables:
        print(describe(args.list_tables))
        return 0
    if args.xlsx_mapping_template:
        print(json.dumps(mapping_template(args.xlsx_mapping_template), indent=2))
        return 0
    baseline_command = bool(args.create_baseline or args.list_baselines)
    review_command = [flag for flag in REVIEW_FLAGS if getattr(args, flag)]
    if review_command:
        names = ", ".join("--" + flag.replace("_", "-") for flag in REVIEW_FLAGS)
        if len(review_command) > 1 or baseline_command or args.check_gate or args.old or args.new or args.extract_comments or args.baselines:
            raise ConfigError(
                f"{names} cannot be combined with each other, --create-baseline, --list-baselines, --check-gate, "
                "--baselines, --old, --new or --extract-comments"
            )
    if (args.role or args.decision or args.note or args.evidence) and not args.sign_off:
        raise ConfigError("--role, --decision, --note and --evidence apply only to --sign-off")
    if args.user and not (args.sign_off or args.waive):
        raise ConfigError("--user applies only to --sign-off and --waive")
    if (args.waive or args.reason is not None) and not args.create_baseline:
        raise ConfigError("--waive and --reason apply only to --create-baseline")
    if args.reason is not None and not args.waive:
        raise ConfigError("--reason applies only with --waive")
    if args.system and not (args.create_baseline or args.check_gate):
        raise ConfigError("--system applies only to --create-baseline and --check-gate")
    if not args.output and not baseline_command and not args.check_gate and not review_command:
        raise ConfigError("--output is required")
    selection = XlsxSelection(args.table, args.sheet, args.header_row)
    inputs = [path for path in (args.input, args.old, args.new) if path]
    if selection.given and not any(is_xlsx(path) for path in inputs):
        raise ConfigError("--table, --sheet and --header-row apply only to .xlsx inputs")
    config = load_config(args.config, _overrides(args))
    if selection.given and config["xlsx"]["sources"]:
        raise ConfigError("--table, --sheet and --header-row cannot be combined with xlsx.sources in the configuration")
    if review_command:
        return run_review_command(args, selection, config)
    if args.check_gate:
        return run_check_gate(args, selection, config)
    if baseline_command:
        return run_baseline_command(args, selection, config)
    if args.extract_comments:
        if args.input or args.old or args.new:
            raise ConfigError("--extract-comments cannot be combined with CSV inputs")
        extract_comments_csv(
            args.extract_comments,
            args.output,
            config["comments"]["csv_column"],
            config["comments"]["csv_format"],
            args.csv_base,
            args.allow_comment_loss,
            config["csv"]["delimiter"],
        )
        return 0
    diff_mode = bool(args.old or args.new)
    if diff_mode:
        if not args.old or not args.new or args.input:
            raise ConfigError("diff mode requires --old and --new and no positional input")
        if args.old.startswith("git:"):
            if is_xlsx(args.old) or is_xlsx(args.new):
                raise InputError("git baselines need CSV for now; export the .xlsx to CSV and commit that")
            old_source = git_source(args.old, args.new, config)
        else:
            old_source = input_source(args.old, selection, config)
        old = read_csv_source(old_source, config)
        new = read_csv_source(input_source(args.new, selection, config), config)
    else:
        if not args.input:
            raise ConfigError("snapshot mode requires an input CSV")
        old = None
        source = input_source(args.input, selection, config)
        new = read_csv_source(source, config)
        if is_xlsx(args.input) and args.output.lower().endswith(".csv"):
            # Same bytes the browser's Save CSV writes: BOM and CRLF.
            assert source.text is not None
            atomic_write_text(args.output, "\ufeff" + source.text)
            return 0
    store = table_store(args.new if diff_mode else args.input, selection, config)
    embedded = []
    if args.baselines:
        names = [name.strip() for name in args.baselines.split(",") if name.strip()]
        embedded = load_baselines(store, config, names)
    controls = build_controls(store, config)
    data = build_report_data(new, config, Path(args.output).name, old=old, baselines=embedded, controls=controls)
    for warning in data["meta"].get("warnings", []):
        print(f"warning: {warning}", file=sys.stderr)
    atomic_write_text(args.output, render_report(data))
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        return run(argv)
    except (ConfigError, argparse.ArgumentError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    except OutputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4
    except ReqtableError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 5
    except Exception as exc:
        print(f"error: unexpected internal error: {exc}", file=sys.stderr)
        return 5
