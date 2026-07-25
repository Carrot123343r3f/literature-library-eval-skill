"""Stable shared components for literature-library evaluation workflows."""

from .contracts import compact, public_value, validate_run_config
from .rendering import render_markdown_html

__all__ = ["compact", "public_value", "render_markdown_html", "validate_run_config"]
