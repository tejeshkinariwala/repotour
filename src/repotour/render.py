# Writes the final HTML: loads the template, swaps the data placeholder for the JSON, saves the file.
from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

PLACEHOLDER = "/*REPOTOUR_DATA*/null"


class RenderError(Exception):
    """The template is missing, has no data placeholder, or the output cannot be written."""


def load_template(template_path: Path | None = None) -> str:
    """Read the packaged template, or the file at template_path (used by tests)."""
    if template_path is not None:
        try:
            return template_path.read_text(encoding="utf-8")
        except OSError as err:
            raise RenderError(f"template not found: {template_path}") from err
    try:
        return resources.files("repotour").joinpath("templates/tour.html").read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError, OSError) as err:
        raise RenderError(
            "template not found: repotour/templates/tour.html is missing from the package"
        ) from err


def render_html(data: dict[str, Any], template_path: Path | None = None) -> str:
    template = load_template(template_path)
    if PLACEHOLDER not in template:
        raise RenderError(f"template has no {PLACEHOLDER} placeholder")
    # Escaping every "<" keeps repo text such as "</script>" or "<!--" from breaking the script tag.
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")
    return template.replace(PLACEHOLDER, payload)


def write_html(data: dict[str, Any], out: Path, template_path: Path | None = None) -> None:
    html = render_html(data, template_path)
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
    except OSError as err:
        raise RenderError(f"{out}: cannot write output: {err.strerror or err}") from err
