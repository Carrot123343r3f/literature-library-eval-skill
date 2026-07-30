"""Cross-platform subprocess defaults for the test suite.

Windows' console code page must not decide how Python test subprocess output is
decoded.  Every child is forced to UTF-8, and captured text is decoded as UTF-8
unless an individual test explicitly requests another encoding.
"""
import os
import subprocess


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
