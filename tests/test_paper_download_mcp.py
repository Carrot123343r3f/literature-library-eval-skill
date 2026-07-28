import os
import sys
from pathlib import Path


def test_queue_server_imports_with_isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setenv("ACADEMIC_MCP_ROOT", str(tmp_path / "library"))
    monkeypatch.setenv("ACADEMIC_MCP_ALLOWED_HOSTS", "example.org")
    # The module reads configuration at import time; reload it in isolation.
    sys.modules.pop("paper_download_mcp.server", None)
    import paper_download_mcp.server as server

    item = server.add_to_download_queue("Example paper", "https://example.org/paper.pdf", "10.1/test")
    assert item["status"] == "queued"
    assert server.list_download_queue()[0]["doi"] == "10.1/test"
    assert server.list_download_queue(status="completed") == []


def test_url_policy_rejects_credentials_and_unapproved_hosts(tmp_path, monkeypatch):
    monkeypatch.setenv("ACADEMIC_MCP_ROOT", str(tmp_path / "library"))
    monkeypatch.setenv("ACADEMIC_MCP_ALLOWED_HOSTS", "example.org")
    sys.modules.pop("paper_download_mcp.server", None)
    import paper_download_mcp.server as server

    try:
        server.validate_url("https://user:password@example.org/paper.pdf")
        assert False, "embedded credentials should be rejected"
    except ValueError as exc:
        assert "credentials" in str(exc)

    try:
        server.validate_url("https://publisher.example/paper.pdf")
        assert False, "unapproved host should be rejected"
    except ValueError as exc:
        assert "allow-listed" in str(exc)

