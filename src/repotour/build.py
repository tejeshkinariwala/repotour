# Assembles the data model (SPEC section 4) that the HTML template renders.
# Pipeline: load config -> scan and parse files -> lay out parts and problems -> resolve stories ->
# apply notes -> compute stats and part links -> collect warnings.
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from repotour import __version__
from repotour.analyzers.base import FileFacts, Item
from repotour.config import Config, load_config
from repotour.globs import is_pattern
from repotour.layout import Layout, auto_layout, expand_pattern, written_layout
from repotour.notes import apply_notes, coverage_warnings, purpose_of
from repotour.repo import RepoFacts, collect_facts
from repotour.roles import merge_roles

TOOL_URL = "https://github.com/tejeshkinariwala/repotour"


def build_data(root: Path) -> dict[str, Any]:
    """Run the whole engine on a repo and return the JSON-ready data model."""
    config = load_config(root)
    repo = collect_facts(root, config)
    return assemble(root, config, repo)


def assemble(root: Path, config: Config, repo: RepoFacts) -> dict[str, Any]:
    written = config.tour is not None
    note_warnings = apply_notes(repo, config.notes)
    if written:
        note_warnings += coverage_warnings(repo, config.notes)
    if config.tour is not None:
        layout = written_layout(config.tour, repo.files)
    else:
        layout = auto_layout(repo.files, repo.roles)
    stories, story_files, story_warnings = _stories(config, repo, layout)
    files = {path: _file_record(path, repo, layout, config, story_files) for path in repo.files}
    parts = _parts_with_counts(layout, repo)
    warnings = repo.warnings + layout.warnings + story_warnings + note_warnings
    return {
        "tool": {"name": "RepoTour", "version": __version__, "url": TOOL_URL},
        "mode": "written" if written else "auto",
        "project": _project(root, config),
        "built_at": local_time_now(),
        "stats": _stats(repo),
        "roles": merge_roles(config.tour.roles if config.tour else []),
        "parts": parts,
        "part_links": _part_links(repo, layout),
        "problems": layout.problems,
        "stories": stories,
        "guide": config.tour.guide if config.tour else [],
        "files": files,
        "warnings": warnings,
    }


def local_time_now() -> str:
    """Local time with numeric UTC offset, e.g. 2026-09-29 14:03 +08:00 (no zone name)."""
    now = datetime.now().astimezone()
    offset = now.strftime("%z")
    return f"{now:%Y-%m-%d %H:%M} {offset[:3]}:{offset[3:]}"


# ---------------------------------------------------------------- pieces


def _project(root: Path, config: Config) -> dict[str, Any]:
    raw = config.tour.project if config.tour else {}

    def text(key: str) -> str:
        value = raw.get(key)
        return "" if value is None else str(value).strip()

    return {
        "name": text("name") or root.resolve().name,
        "tagline": text("tagline"),
        "overview": text("overview"),
        "repo_url": text("repo_url") or None,
        "branch": text("branch") or "main",
    }


def _stats(repo: RepoFacts) -> dict[str, Any]:
    languages: dict[str, int] = {}
    for facts in repo.facts.values():
        languages[facts.lang] = languages.get(facts.lang, 0) + 1
    ordered = dict(sorted(languages.items(), key=lambda pair: (-pair[1], pair[0])))
    return {
        "files": len(repo.files),
        "lines": sum(f.lines for f in repo.facts.values()),
        "languages": ordered,
    }


def _stories(
    config: Config, repo: RepoFacts, layout: Layout
) -> tuple[list[dict[str, Any]], dict[str, list[str]], list[str]]:
    """Resolve story step patterns to files. Returns (stories, path -> story ids, warnings)."""
    stories: list[dict[str, Any]] = []
    story_files: dict[str, list[str]] = {}
    warnings: list[str] = []
    file_set = set(repo.files)
    for story in config.tour.stories if config.tour else []:
        steps = []
        for number, step in enumerate(story["steps"], start=1):
            found: list[str] = []
            for pattern in step["files"]:
                matched = expand_pattern(pattern, repo.files, file_set)
                where = f"tour.yaml: story '{story['id']}' step {number}"
                if not matched:
                    what = (
                        "matches no file" if is_pattern(pattern) or pattern.endswith("/") else "no such file"
                    )
                    warnings.append(f"{where}: '{pattern}': {what}")
                for path in matched:
                    if path in found:
                        continue
                    found.append(path)
                    if path not in layout.listed:
                        warnings.append(f"{where}: {path} is not under any problem")
                    ids = story_files.setdefault(path, [])
                    if story["id"] not in ids:
                        ids.append(story["id"])
            steps.append({"text": step["text"], "files": found})
        stories.append({**story, "steps": steps})
    return stories, story_files, warnings


def _file_record(
    path: str, repo: RepoFacts, layout: Layout, config: Config, story_files: dict[str, list[str]]
) -> dict[str, Any]:
    facts = repo.facts[path]
    record: dict[str, Any] = {
        "lang": facts.lang,
        "lines": facts.lines,
        "purpose": purpose_of(facts, config.notes.get(path)),
        "role": repo.roles[path],
        "problem": layout.file_problem.get(path),
        "part": layout.file_part.get(path),
        "stories": story_files.get(path, []),
    }
    if facts.items is not None:
        record["outline"] = outline_json(facts)
    record["imports"] = imports_json(facts)
    record["libs"] = facts.libs
    record["used_by"] = repo.used_by.get(path, [])
    return record


def outline_json(facts: FileFacts) -> dict[str, Any]:
    return {"items": [item_json(i) for i in facts.items or []], "consts": facts.consts}


def item_json(item: Item) -> dict[str, Any]:
    return {
        "name": item.name,
        "kind": item.kind,
        "line": item.line,
        "signature": item.signature,
        "note": item.note,
        "exported": item.exported,
        "methods": [
            {"name": m.name, "line": m.line, "signature": m.signature, "note": m.note} for m in item.methods
        ],
        "calls": item.calls,
        "children": [item_json(c) for c in item.children],
    }


def imports_json(facts: FileFacts) -> list[dict[str, Any]]:
    return [{"file": target, "names": names} for target, names in sorted(facts.imports.items())]


def _parts_with_counts(layout: Layout, repo: RepoFacts) -> list[dict[str, Any]]:
    counts: dict[str, list[int]] = {}
    for path, part_id in layout.file_part.items():
        entry = counts.setdefault(part_id, [0, 0])
        entry[0] += 1
        entry[1] += repo.facts[path].lines
    parts = []
    for part in layout.parts:
        files, lines = counts.get(part["id"], [0, 0])
        parts.append(
            {
                "id": part["id"],
                "name": part["name"],
                "role": part["role"],
                "summary": part["summary"],
                "folders": part["folders"],
                "color": part["color"],
                "problems": part["problems"],
                "files": files,
                "lines": lines,
            }
        )
    return parts


def _part_links(repo: RepoFacts, layout: Layout) -> list[dict[str, Any]]:
    """Count file-to-file import edges that cross from one part into another."""
    edges: dict[tuple[str, str], int] = {}
    for path in repo.files:
        source = layout.file_part.get(path)
        for target in repo.facts[path].imports:
            dest = layout.file_part.get(target)
            if source and dest and source != dest:
                edges[(source, dest)] = edges.get((source, dest), 0) + 1
    order = {p["id"]: i for i, p in enumerate(layout.parts)}
    ranked = sorted(edges.items(), key=lambda kv: (order[kv[0][0]], order[kv[0][1]]))
    return [{"from": a, "to": b, "imports": n} for (a, b), n in ranked]
