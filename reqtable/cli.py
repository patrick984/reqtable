from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from . import __version__
from .core import (
    DEFAULT_CONFIG,
    ConfigError,
    CsvSource,
    InputError,
    OutputError,
    ReqtableError,
    atomic_write_text,
    build_report_data,
    extract_comments_csv,
    load_config,
    read_csv_source,
)
from .html_report import render_report


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Generate an offline requirements table or diff report.")
    result.add_argument("input", nargs="?", help="CSV input for snapshot mode")
    result.add_argument("--old", help="old/baseline CSV for diff mode, or git:REV[:PATH] to read it from a git revision")
    result.add_argument("--new", help="new/current CSV for diff mode")
    result.add_argument("--extract-comments", metavar="REPORT.html", help="extract comments from a generated report")
    result.add_argument("-o", "--output", help="output HTML or CSV path")
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


def _git(directory: Path, *args: str) -> bytes:
    try:
        completed = subprocess.run(["git", "-C", str(directory), *args], capture_output=True)
    except OSError as exc:
        raise InputError(f"cannot run git: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise InputError(f"git {args[0]} failed: {detail}")
    return completed.stdout


def git_source(spec: str, default_path: str, config: dict[str, object]) -> CsvSource:
    """Resolve git:REV[:PATH]; PATH defaults to the --new file's path."""
    rev, _, given = spec[len("git:"):].partition(":")
    if not rev:
        raise ConfigError("--old git: needs a revision, as git:REV or git:REV:PATH")
    path = Path(given or default_path)
    try:
        # --filters applies the repo's eol/attribute rules, as for a checked-out file.
        blob = _git(path.parent, "cat-file", "--filters", f"{rev}:./{path.name}")
        short = _git(path.parent, "rev-parse", "--short", f"{rev}^{{commit}}").decode().strip()
    except InputError as exc:
        raise InputError(f"cannot read {path} at {rev}: {exc}") from exc
    encoding = config["csv"]["encoding"]  # type: ignore[index]
    label = f"{path.name} @ {rev} ({short})"
    try:
        return CsvSource(label, blob.decode(encoding), path)
    except (UnicodeError, LookupError) as exc:
        raise InputError(f"{label}: cannot decode as {encoding}: {exc}") from exc


def file_source(path: str) -> CsvSource:
    return CsvSource(str(Path(path)), None, Path(path))


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.print_default_config:
        print(json.dumps(DEFAULT_CONFIG, indent=2))
        return 0
    if not args.output:
        raise ConfigError("--output is required")
    config = load_config(args.config, _overrides(args))
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
        old_source = git_source(args.old, args.new, config) if args.old.startswith("git:") else file_source(args.old)
        old = read_csv_source(old_source, config)
        new = read_csv_source(file_source(args.new), config)
    else:
        if not args.input:
            raise ConfigError("snapshot mode requires an input CSV")
        old = None
        new = read_csv_source(file_source(args.input), config)
    data = build_report_data(new, config, Path(args.output).name, old=old)
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
