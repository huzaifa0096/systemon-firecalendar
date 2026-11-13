"""Convert a simple Markdown file to a styled HTML file (for printing to PDF with Edge/Chrome).
Usage: python scripts/md_to_pdf.py input.md output.html
Supports: headings, tables, lists, code blocks, bold, inline code, links, hr, paragraphs.
"""
import html
import re
import sys

src, out = sys.argv[1], sys.argv[2]
lines = open(src, encoding="utf-8").read().splitlines()


def inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"(?<![\"'>=])(https?://[^\s<)]+)", r'<a href="\1">\1</a>', t)
    return t


body, i = [], 0
while i < len(lines):
    ln = lines[i]
    s = ln.strip()
    if s.startswith("```"):
        i += 1
        code = []
        while i < len(lines) and not lines[i].strip().startswith("```"):
            code.append(html.escape(lines[i]))
            i += 1
        body.append("<pre>" + "\n".join(code) + "</pre>")
    elif s.startswith("|"):
        rows = []
        while i < len(lines) and lines[i].strip().startswith("|"):
            rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
            i += 1
        i -= 1
        h = "".join(f"<th>{inline(c)}</th>" for c in rows[0])
        b = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows[2:])
        body.append(f"<table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>")
    elif m := re.match(r"^(#{1,6})\s+(.*)", s):
        n = len(m.group(1))
        body.append(f"<h{n}>{inline(m.group(2))}</h{n}>")
    elif s.startswith(">"):
        body.append("<blockquote>" + inline(s.lstrip("> ").strip()) + "</blockquote>")
    elif s == "---":
        body.append("<hr>")
    elif re.match(r"^(\d+\.|-)\s+", s):
        tag = "ol" if s[0].isdigit() else "ul"
        items = []
        while i < len(lines) and re.match(r"^\s*(\d+\.|-)\s+", lines[i]):
            raw = lines[i]
            sub = raw.startswith("   ") or raw.startswith("  -")
            txt = re.sub(r"^\s*(\d+\.|-)\s+", "", raw)
            items.append(("sub" if sub else "") + "<li>" + inline(txt) + "</li>")
            i += 1
        i -= 1
        html_items = []
        in_sub = False
        for it in items:
            if it.startswith("sub"):
                if not in_sub:
                    html_items.append("<ul>")
                    in_sub = True
                html_items.append(it[3:])
            else:
                if in_sub:
                    html_items.append("</ul>")
                    in_sub = False
                html_items.append(it)
        if in_sub:
            html_items.append("</ul>")
        body.append(f"<{tag}>" + "".join(html_items) + f"</{tag}>")
    elif s:
        para = [s]
        while i + 1 < len(lines) and lines[i + 1].strip() and not s.endswith("**") and not re.match(r"^(#|\||```|---|>|\d+\.\s|-\s)", lines[i + 1].strip()):
            i += 1
            para.append(lines[i].strip())
        body.append("<p>" + inline(" ".join(para)) + "</p>")
    i += 1

css = """
@page { size: A4; margin: 16mm 14mm; }
body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 11pt; line-height: 1.5; color: #1a1a1a; }
h1 { font-size: 22pt; color: #b3261e; margin: 0 0 4px; }
h3 { font-size: 13pt; color: #444; margin-top: 4px; page-break-after: avoid; break-after: avoid; }
h3 + table, h3 + pre { break-before: avoid; }
h2 { font-size: 15pt; color: #fff; background: #b3261e; padding: 6px 10px; border-radius: 4px; margin-top: 22px; page-break-after: avoid; }
h2 + * { page-break-before: avoid; }
table { border-collapse: collapse; width: 100%; margin: 8px 0 12px; font-size: 9.5pt; page-break-inside: avoid; }
th { background: #f3e1df; text-align: left; }
th, td { border: 1px solid #ccc; padding: 4px 6px; vertical-align: top; word-break: break-word; }
td:first-child, th:first-child { white-space: nowrap; word-break: normal; }
tr:nth-child(even) td { background: #fafafa; }
code { background: #f1f1f1; padding: 1px 4px; border-radius: 3px; font-family: Consolas, monospace; font-size: 9.5pt; }
pre { background: #f6f6f6; border: 1px solid #ddd; padding: 8px; font-size: 8.5pt; white-space: pre-wrap; word-break: break-all; font-family: Consolas, monospace; }
a { color: #0b57d0; word-break: break-all; }
hr { border: none; border-top: 1px solid #ddd; margin: 14px 0; }
li { margin: 2px 0; }
blockquote { border-left: 4px solid #b3261e; background: #fbf1f0; margin: 8px 0; padding: 8px 12px; font-style: italic; }
"""
doc = f"<!doctype html><html><head><meta charset='utf-8'><title>NASA Space Apps 2026 Research</title><style>{css}</style></head><body>{''.join(body)}</body></html>"
open(out, "w", encoding="utf-8").write(doc)
print("wrote", out)
