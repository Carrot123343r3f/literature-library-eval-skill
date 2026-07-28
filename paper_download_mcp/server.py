"""A small local MCP server for a controlled academic-paper download queue.

Security properties:
- stores data in a configured directory, never an arbitrary user path;
- requires an explicit host allow-list before downloading;
- accepts only http(s) URLs without embedded credentials;
- never exposes a shell or browser cookies through MCP;
- caps download size and rejects non-PDF responses unless configured otherwise.

This server is intentionally a queue/download backend. Institutional SSO, MFA,
campus proxy, and publisher-specific browser flows should be handled by a
separate local browser adapter, not by sending credentials to the model.
"""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


APP_NAME = "academic-paper-download"
# Keep the default portable and writable in a checked-out project. Production
# deployments should set ACADEMIC_MCP_ROOT explicitly (for example,
# C:\\AcademicLibrary on Windows).
DEFAULT_ROOT = Path(os.environ.get("ACADEMIC_MCP_ROOT", Path.cwd() / "academic-library-data"))
DB_PATH = DEFAULT_ROOT / "queue.sqlite3"
PDF_DIR = DEFAULT_ROOT / "papers"
MAX_DOWNLOAD_BYTES = int(os.environ.get("ACADEMIC_MCP_MAX_BYTES", str(100 * 1024 * 1024)))
ALLOWED_HOSTS = {
    host.strip().lower().lstrip(".")
    for host in os.environ.get("ACADEMIC_MCP_ALLOWED_HOSTS", "").split(",")
    if host.strip()
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_storage() -> None:
    DEFAULT_ROOT.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(DB_PATH)) as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS papers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                doi TEXT,
                url TEXT NOT NULL,
                status TEXT NOT NULL,
                file_path TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(url)
            )"""
        )
        db.commit()


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def validate_url(url: str) -> urllib.parse.ParseResult:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("url must be an http(s) URL")
    if parsed.username or parsed.password:
        raise ValueError("embedded credentials in URLs are not allowed")
    if not ALLOWED_HOSTS:
        raise ValueError(
            "download host allow-list is empty; set ACADEMIC_MCP_ALLOWED_HOSTS first"
        )
    hostname = parsed.hostname.lower().rstrip(".")
    if not any(hostname == allowed or hostname.endswith("." + allowed) for allowed in ALLOWED_HOSTS):
        raise ValueError(f"download host is not allow-listed: {hostname}")
    return parsed


def safe_filename(title: str, paper_id: int, url: str) -> str:
    cleaned = re.sub(r"[^\w\-. ]+", "", title, flags=re.UNICODE).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)[:120] or "paper"
    suffix = Path(urllib.parse.urlparse(url).path).suffix.lower()
    if suffix not in {".pdf", ".txt"}:
        suffix = ".pdf"
    return f"{paper_id:06d}-{cleaned}{suffix}"


def get_paper(paper_id: int) -> dict[str, Any] | None:
    ensure_storage()
    with closing(sqlite3.connect(DB_PATH)) as db:
        db.row_factory = sqlite3.Row
        row = db.execute("SELECT * FROM papers WHERE id = ?", (paper_id,)).fetchone()
        return row_to_dict(row) if row else None


def update_paper(paper_id: int, **values: Any) -> None:
    values["updated_at"] = now()
    assignments = ", ".join(f"{key} = ?" for key in values)
    with closing(sqlite3.connect(DB_PATH)) as db:
        db.execute(
            f"UPDATE papers SET {assignments} WHERE id = ?",
            (*values.values(), paper_id),
        )
        db.commit()


def download_paper(paper_id: int) -> dict[str, Any]:
    paper = get_paper(paper_id)
    if not paper:
        raise ValueError(f"paper not found: {paper_id}")
    parsed = validate_url(paper["url"])
    update_paper(paper_id, status="downloading", error=None)
    target = PDF_DIR / safe_filename(paper["title"], paper_id, paper["url"])
    temp = target.with_suffix(target.suffix + ".part")
    try:
        request = urllib.request.Request(
            paper["url"],
            headers={"User-Agent": "academic-paper-download-mcp/0.1"},
        )
        with urllib.request.urlopen(request, timeout=60) as response, temp.open("wb") as output:
            # DOI and publisher links commonly redirect. Re-validate the final
            # host so redirects cannot escape the configured allow-list.
            validate_url(response.geturl())
            content_type = response.headers.get_content_type()
            if content_type not in {"application/pdf", "application/octet-stream", "text/plain"}:
                raise ValueError(f"response is not a PDF/file (content-type: {content_type})")
            total = 0
            digest = hashlib.sha256()
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    raise ValueError(f"download exceeds limit of {MAX_DOWNLOAD_BYTES} bytes")
                output.write(chunk)
                digest.update(chunk)
        temp.replace(target)
        update_paper(
            paper_id,
            status="completed",
            file_path=str(target),
            error=None,
        )
        return {**get_paper(paper_id), "sha256": digest.hexdigest(), "bytes": total}
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        temp.unlink(missing_ok=True)
        update_paper(paper_id, status="failed", error=str(exc))
        return get_paper(paper_id) or {"id": paper_id, "status": "failed", "error": str(exc)}


def extract_pdf_text(path: Path, max_chars: int) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("PDF text extraction requires pypdf; install requirements.txt") from exc
    reader = PdfReader(str(path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return text[:max_chars]


ensure_storage()
mcp = FastMCP(
    APP_NAME,
    instructions=(
        "Manage a local, allow-listed academic paper download queue. "
        "Do not request or handle passwords, cookies, or MFA codes. "
        "Institutional-login downloads may require a local browser adapter."
    ),
    host=os.environ.get("ACADEMIC_MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("ACADEMIC_MCP_PORT", "8000")),
    streamable_http_path="/mcp",
)


@mcp.tool()
def add_to_download_queue(title: str, url: str, doi: str | None = None) -> dict[str, Any]:
    """Add one paper URL to the local queue; does not download it."""
    validate_url(url)
    if not title.strip():
        raise ValueError("title must not be empty")
    ensure_storage()
    timestamp = now()
    with closing(sqlite3.connect(DB_PATH)) as db:
        db.row_factory = sqlite3.Row
        existing = db.execute("SELECT * FROM papers WHERE url = ?", (url,)).fetchone()
        if existing:
            return {**row_to_dict(existing), "deduplicated": True}
        cursor = db.execute(
            """INSERT INTO papers(title, doi, url, status, created_at, updated_at)
               VALUES (?, ?, ?, 'queued', ?, ?)""",
            (title.strip(), doi, url, timestamp, timestamp),
        )
        db.commit()
        paper_id = int(cursor.lastrowid)
    return get_paper(paper_id) or {"id": paper_id, "status": "queued"}


@mcp.tool()
def list_download_queue(status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """List queued/completed/failed papers, newest first."""
    ensure_storage()
    limit = max(1, min(int(limit), 500))
    with closing(sqlite3.connect(DB_PATH)) as db:
        db.row_factory = sqlite3.Row
        if status:
            rows = db.execute(
                "SELECT * FROM papers WHERE status = ? ORDER BY id DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = db.execute("SELECT * FROM papers ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [row_to_dict(row) for row in rows]


@mcp.tool()
def start_download(paper_id: int) -> dict[str, Any]:
    """Download one queued paper from an allow-listed URL."""
    return download_paper(int(paper_id))


@mcp.tool()
def get_download_status(paper_id: int) -> dict[str, Any]:
    """Return the status and error, if any, for one paper."""
    paper = get_paper(int(paper_id))
    if not paper:
        raise ValueError(f"paper not found: {paper_id}")
    return paper


@mcp.tool()
def list_completed_files(limit: int = 100) -> list[dict[str, Any]]:
    """List completed files inside the configured paper directory."""
    return [
        {"name": path.name, "path": str(path), "bytes": path.stat().st_size}
        for path in sorted(PDF_DIR.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True)
        if path.is_file() and path.suffix.lower() in {".pdf", ".txt"}
    ][: max(1, min(int(limit), 500))]


@mcp.tool()
def read_downloaded_pdf(paper_id: int, max_chars: int = 30000) -> dict[str, Any]:
    """Extract text from a completed local PDF for summarization."""
    paper = get_paper(int(paper_id))
    if not paper:
        raise ValueError(f"paper not found: {paper_id}")
    if paper["status"] != "completed" or not paper["file_path"]:
        raise ValueError("paper is not completed")
    path = Path(paper["file_path"]).resolve()
    if PDF_DIR.resolve() not in path.parents:
        raise ValueError("file is outside the configured paper directory")
    return {"paper": paper, "text": extract_pdf_text(path, max(1000, min(int(max_chars), 100000)))}


if __name__ == "__main__":
    transport = os.environ.get("ACADEMIC_MCP_TRANSPORT", "streamable-http")
    if transport not in {"stdio", "sse", "streamable-http"}:
        raise SystemExit("ACADEMIC_MCP_TRANSPORT must be stdio, sse, or streamable-http")
    mcp.run(transport=transport)
