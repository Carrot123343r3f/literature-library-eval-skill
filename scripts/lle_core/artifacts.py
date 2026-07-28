"""Artifact hashing and lineage records for workflow runs."""
from __future__ import annotations

import hashlib
import pathlib


def sha256_file(path):
    digest = hashlib.sha256()
    with pathlib.Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_record(root, path, producer, kind="output"):
    root = pathlib.Path(root).resolve()
    path = pathlib.Path(path).resolve()
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError(f"artifact path escapes workflow root: {path}") from exc
    if not path.is_file():
        raise ValueError(f"artifact does not exist: {path}")
    return {"path": relative, "sha256": sha256_file(path), "size": path.stat().st_size,
            "producer": producer, "kind": kind}
