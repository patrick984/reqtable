from __future__ import annotations

import html
import re


_SAFE_LINK = re.compile(r"^(?:https?://|mailto:)", re.IGNORECASE)


def _inline(text: str) -> str:
    escaped = html.escape(text, quote=True)
    code_values: list[str] = []

    def save_code(match: re.Match[str]) -> str:
        code_values.append(f"<code>{match.group(1)}</code>")
        return f"\x00CODE{len(code_values) - 1}\x00"

    escaped = re.sub(r"`([^`\n]+)`", save_code, escaped)

    def link(match: re.Match[str]) -> str:
        label, target = match.group(1), html.unescape(match.group(2)).strip()
        if _SAFE_LINK.match(target):
            return f'<a href="{html.escape(target, quote=True)}">{label}</a>'
        return f"{label} ({html.escape(target)})"

    escaped = re.sub(r"\[([^\]\n]+)\]\(([^)\n]+)\)", link, escaped)
    escaped = re.sub(r"\*\*([^*\n]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"__([^_\n]+)__", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", escaped)
    escaped = re.sub(r"(?<!_)_([^_\n]+)_(?!_)", r"<em>\1</em>", escaped)
    for index, value in enumerate(code_values):
        escaped = escaped.replace(f"\x00CODE{index}\x00", value)
    return escaped


def render_markdown(source: str) -> str:
    """Render the deliberately small, safe Markdown subset used by reports."""
    if source == "":
        return '<span class="empty-value">Empty</span>'
    lines = source.split("\n")
    output: list[str] = []
    paragraph: list[str] = []
    list_type: str | None = None
    quote_lines: list[str] = []
    code_lines: list[str] | None = None

    def flush_paragraph() -> None:
        if paragraph:
            output.append("<p>" + "<br>".join(_inline(line) for line in paragraph) + "</p>")
            paragraph.clear()

    def close_list() -> None:
        nonlocal list_type
        if list_type:
            output.append(f"</{list_type}>")
            list_type = None

    def flush_quote() -> None:
        if quote_lines:
            output.append("<blockquote>" + "<br>".join(_inline(line) for line in quote_lines) + "</blockquote>")
            quote_lines.clear()

    for line in lines:
        if code_lines is not None:
            if line.startswith("```"):
                output.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
                code_lines = None
            else:
                code_lines.append(line)
            continue
        if line.startswith("```"):
            flush_paragraph(); close_list(); flush_quote(); code_lines = []
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            flush_paragraph(); close_list(); flush_quote()
            level = min(6, len(heading.group(1)) + 2)
            output.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            continue
        item = re.match(r"^\s*([-+*])\s+(.+)$", line)
        ordered = re.match(r"^\s*\d+[.)]\s+(.+)$", line)
        if item or ordered:
            flush_paragraph(); flush_quote()
            desired = "ul" if item else "ol"
            if list_type != desired:
                close_list(); output.append(f"<{desired}>"); list_type = desired
            output.append(f"<li>{_inline((item or ordered).group(2 if item else 1))}</li>")
            continue
        if line.startswith(">"):
            flush_paragraph(); close_list(); quote_lines.append(line[1:].lstrip())
            continue
        if line.strip() == "":
            flush_paragraph(); close_list(); flush_quote()
        else:
            close_list(); flush_quote(); paragraph.append(line)
    if code_lines is not None:
        output.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
    flush_paragraph(); close_list(); flush_quote()
    return "".join(output)

