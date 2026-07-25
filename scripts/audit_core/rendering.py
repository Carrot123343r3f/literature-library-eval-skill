"""Dependency-free rendering for generated Markdown reports."""
import html
import re


def render_markdown_html(markdown_text, title="文献库评价报告"):
    """Render the supported Markdown subset as a standalone, escaped HTML report."""
    def inline(value):
        escaped = html.escape(value)
        escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
        return re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)

    lines = markdown_text.splitlines()
    parts = [f"<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>{html.escape(title)}</title><style>"
             "body{margin:0;background:#f6f8fb;color:#172033;font:15px/1.6 -apple-system,BlinkMacSystemFont,'Segoe UI','Microsoft YaHei',sans-serif}"
             "main{max-width:1440px;margin:32px auto;padding:32px;background:#fff;border-radius:14px;box-shadow:0 8px 28px #1f355018}"
             "h1{font-size:30px;margin:0 0 24px;color:#112a46}h2{margin-top:36px;padding-bottom:8px;border-bottom:2px solid #dce7f3;color:#133b63}h3{margin-top:28px;color:#24567f}h4{margin-top:22px}"
             "p{margin:10px 0}blockquote{margin:16px 0;padding:12px 16px;background:#eef6ff;border-left:4px solid #3b82c4;border-radius:4px}"
             "ul{margin:8px 0 16px;padding-left:24px}.table-wrap{overflow-x:auto;margin:14px 0 24px}table{width:100%;border-collapse:collapse;font-size:13px}th{background:#173f68;color:#fff;text-align:left}th,td{padding:9px 10px;vertical-align:top;border:1px solid #d9e2ec}tr:nth-child(even){background:#f8fbfe}code{padding:1px 4px;background:#eef2f6;border-radius:3px;font-family:ui-monospace,Consolas,monospace}strong{color:#9b2c2c}@media(max-width:760px){main{margin:0;padding:18px;border-radius:0}h1{font-size:24px}table{font-size:12px}}</style><main>"]
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("|") and index + 1 < len(lines) and re.match(r"^\|[ -:|]+\|$", lines[index + 1]):
            headers = [cell.strip() for cell in line.strip("|").split("|")]
            index += 2; body = []
            while index < len(lines) and lines[index].startswith("|"):
                body.append([cell.strip() for cell in lines[index].strip("|").split("|")]); index += 1
            parts.append("<div class='table-wrap'><table><thead><tr>" + "".join(f"<th>{inline(cell)}</th>" for cell in headers) + "</tr></thead><tbody>")
            parts.extend("<tr>" + "".join(f"<td>{inline(cell)}</td>" for cell in row) + "</tr>" for row in body)
            parts.append("</tbody></table></div>"); continue
        if line.startswith("#### "): parts.append(f"<h4>{inline(line[5:])}</h4>")
        elif line.startswith("### "): parts.append(f"<h3>{inline(line[4:])}</h3>")
        elif line.startswith("## "): parts.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("# "): parts.append(f"<h1>{inline(line[2:])}</h1>")
        elif line.startswith("> "): parts.append(f"<blockquote>{inline(line[2:])}</blockquote>")
        elif line.startswith("- "):
            items = []
            while index < len(lines) and lines[index].startswith("- "):
                items.append(f"<li>{inline(lines[index][2:])}</li>"); index += 1
            parts.append("<ul>" + "".join(items) + "</ul>"); continue
        elif line.strip(): parts.append(f"<p>{inline(line)}</p>")
        index += 1
    return "\n".join(parts + ["</main></html>"])
