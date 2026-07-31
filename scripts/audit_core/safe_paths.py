"""Fail-closed path preparation shared by every public output entry point."""
from __future__ import annotations
import pathlib


def _check_ancestors(path: pathlib.Path):
    if ".." in path.parts:
        raise ValueError("output path must not contain '..'")
    if any(node.exists() and node.is_symlink() for node in (path, *path.parents)):
        raise ValueError("output path must not traverse a symbolic link")


def prepare_output_dir(value, *, force=False, resume=False, state_name=None, allowed_existing=()):
    path = pathlib.Path(value)
    _check_ancestors(path)
    if path.exists() and any(path.iterdir()) and not (force or resume):
        unexpected = {entry.name for entry in path.iterdir()} - set(allowed_existing)
        if unexpected:
            raise ValueError("output directory is not empty; choose a new directory or pass --force")
    if resume and state_name and not (path / state_name).is_file():
        raise ValueError(f"--resume requires an existing {state_name}")
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def prepare_output_file(value, *, force=False, resume=False):
    path = pathlib.Path(value)
    _check_ancestors(path)
    if path.exists() and not (force or resume):
        raise ValueError("output file already exists; choose a new path or pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def prepare_stage_dir(value, *, allowed_existing=(), resume_existing=(), force=False, resume=False):
    """Prepare a controlled stage workspace.

    A fresh invocation can reuse only prerequisite files explicitly named by
    ``allowed_existing``.  A resumed invocation may additionally reuse its own
    verified result files named by ``resume_existing``.  This lets a workflow
    recover after an interrupted stage without treating arbitrary leftovers as
    safe.
    """
    path = pathlib.Path(value)
    _check_ancestors(path)
    if path.exists() and not force:
        permitted = set(allowed_existing)
        if resume:
            permitted |= set(resume_existing)
        unexpected = {item.name for item in path.iterdir()} - permitted
        if unexpected:
            raise ValueError("stage directory contains unexpected files: " + ", ".join(sorted(unexpected)))
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()
