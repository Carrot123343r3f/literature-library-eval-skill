"""Cross-platform subprocess defaults for the test suite.

Windows' console code page must not decide how Python test subprocess output is
decoded.  Every child is forced to UTF-8, and captured text is decoded as UTF-8
unless an individual test explicitly requests another encoding.
"""
import os
import subprocess

import pytest


_run = subprocess.run


def _utf8_run(*args, **kwargs):
    env = dict(os.environ)
    env.update(kwargs.pop("env", {}) or {})
    env.setdefault("PYTHONUTF8", "1")
    kwargs["env"] = env
    if (kwargs.get("text") or kwargs.get("universal_newlines")) and "encoding" not in kwargs:
        kwargs["encoding"] = "utf-8"
        kwargs.setdefault("errors", "replace")
    return _run(*args, **kwargs)


subprocess.run = _utf8_run


def pytest_collection_modifyitems(items):
    """Classify existing tests without coupling correctness to file naming."""
    for item in items:
        filename = item.path.name
        if filename in {"test_run_audit.py", "test_workflow_tools.py", "test_architecture_kernel.py"}:
            item.add_marker(pytest.mark.smoke)
        if filename in {"test_adversarial_inputs.py", "test_security_and_contracts.py", "test_evidence_gates.py"}:
            item.add_marker(pytest.mark.contract_security)
        if filename in {"test_run_full_audit_e2e.py", "test_institutional_source_exports.py"}:
            item.add_marker(pytest.mark.e2e)
