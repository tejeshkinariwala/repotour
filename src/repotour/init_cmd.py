# `repotour init`: writes a starter .repotour/tour.yaml (parts guessed from folders, one
# placeholder problem per part) and a notes.yaml skeleton with an empty note for every outline item.
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from repotour.config import NOTES_FILE, TOUR_FILE, Config, ConfigError
from repotour.layout import auto_parts
from repotour.notes import FILE_KEY, outline_keys
from repotour.repo import RepoFacts, collect_facts

TOUR_HEADER = "# Starter tour written by `repotour init`. Fill in the TODO text, then run `repotour build`.\n"
NOTES_HEADER = "# One-line note per outline item. A file with any note needs a note for every item.\n"


def init_project(root: Path, force: bool) -> list[Path]:
    """Write the starter files. Returns the paths written."""
    tour_path, notes_path = root / TOUR_FILE, root / NOTES_FILE
    existing = [p for p in (tour_path, notes_path) if p.exists()]
    if existing and not force:
        names = ", ".join(str(p.relative_to(root)) for p in existing)
        raise ConfigError(f"{names}: already exists (use --force to overwrite)")
    repo = collect_facts(root, Config())
    tour_path.parent.mkdir(parents=True, exist_ok=True)
    tour_path.write_text(TOUR_HEADER + _dump(_starter_tour(root, repo.files, repo.roles)), encoding="utf-8")
    notes_path.write_text(NOTES_HEADER + _dump(_notes_skeleton(repo)), encoding="utf-8")
    return [tour_path, notes_path]


def _dump(data: dict[str, Any]) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)


def _starter_tour(root: Path, files: list[str], roles: dict[str, str]) -> dict[str, Any]:
    parts, problems = [], []
    counters: dict[str, int] = {}
    for auto in auto_parts(files, roles):
        initial = auto.name[0].upper()
        counters[initial] = counters.get(initial, 0) + 1
        parts.append(
            {"id": auto.id, "name": auto.name, "role": "TODO: one line on the job of this part",
             "folders": auto.folders, "summary": "TODO: 2-4 plain sentences about this part."}
        )  # fmt: skip
        problems.append(
            {"id": f"{initial}{counters[initial]}", "part": auto.id,
             "title": f"TODO: the problem the {auto.name} files solve",
             "without": "TODO: what goes wrong without this code", "fix": "TODO: how these files solve it",
             "files": auto.files}
        )  # fmt: skip
    project = {"name": root.resolve().name, "tagline": "TODO: one sentence on what this repo is for."}
    return {"project": project, "parts": parts, "problems": problems}


def _notes_skeleton(repo: RepoFacts) -> dict[str, dict[str, str]]:
    skeleton: dict[str, dict[str, str]] = {}
    for path in repo.files:
        items = repo.facts[path].items
        if not items:
            continue
        entries = {FILE_KEY: ""}
        for key, _ in outline_keys(items):
            entries[key] = ""
        skeleton[path] = entries
    return skeleton
