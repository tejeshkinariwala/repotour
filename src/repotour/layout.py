# Decides which part and problem every file belongs to.
# Written mode follows tour.yaml (expanding patterns, placing unlisted files); auto mode makes one
# placeholder problem per top-level folder.
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from repotour.config import Tour
from repotour.globs import is_pattern, matches

PALETTE = [
    "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899",
    "#14b8a6", "#f97316", "#6366f1", "#84cc16", "#06b6d4", "#a855f7",
]  # fmt: skip


@dataclass
class Layout:
    parts: list[dict[str, Any]] = field(default_factory=list)  # with "problems": [ids], no counts yet
    problems: list[dict[str, Any]] = field(default_factory=list)
    file_problem: dict[str, str] = field(default_factory=dict)
    file_part: dict[str, str] = field(default_factory=dict)
    listed: set[str] = field(default_factory=set)  # files the author placed under a problem
    warnings: list[str] = field(default_factory=list)


def expand_pattern(pattern: str, files: list[str], file_set: set[str]) -> list[str]:
    """Files matched by one path or pattern (in path order)."""
    pattern = pattern.strip()
    while pattern.startswith("./"):
        pattern = pattern[2:]
    if pattern in file_set:  # a literal file name, even one with glob characters like pages/[id].tsx
        return [pattern]
    if not is_pattern(pattern) and not pattern.endswith("/"):
        return []
    return [f for f in files if matches(f, pattern)]


# ---------------------------------------------------------------- written mode


def written_layout(tour: Tour, files: list[str]) -> Layout:
    layout = Layout(warnings=list(tour.warnings))
    file_set = set(files)
    parts = [dict(p, problems=[]) for p in tour.parts]
    part_by_id = {p["id"]: p for p in parts}
    for i, part in enumerate(parts):
        part["color"] = part["color"] or PALETTE[i % len(PALETTE)]
    problems = [dict(p, placeholder=False) for p in tour.problems]
    for problem in problems:
        part_by_id[problem["part"]]["problems"].append(problem["id"])
        problem["files"], problem["tests"] = _place_problem_files(problem, files, file_set, layout)
    for part in parts:
        if not part["problems"]:
            layout.warnings.append(f"tour.yaml: part '{part['id']}' has no problems")
    for problem in problems:
        if not problem["files"] and not problem["tests"]:
            layout.warnings.append(f"tour.yaml: problem '{problem['id']}' has no files")
    _place_unlisted(files, parts, problems, layout)
    layout.parts = parts
    layout.problems = problems
    for problem in problems:
        for path in problem["files"] + problem["tests"]:
            layout.file_problem[path] = problem["id"]
            layout.file_part[path] = problem["part"]
    return layout


def _place_problem_files(
    problem: dict[str, Any], files: list[str], file_set: set[str], layout: Layout
) -> tuple[list[str], list[str]]:
    kept: dict[str, list[str]] = {"files": [], "tests": []}
    own: set[str] = set()
    for key in ("files", "tests"):
        for pattern in problem[key]:
            matched = expand_pattern(pattern, files, file_set)
            if not matched:
                what = "matches no file" if is_pattern(pattern) or pattern.endswith("/") else "no such file"
                layout.warnings.append(f"tour.yaml: problem '{problem['id']}' {key}: '{pattern}': {what}")
            for path in matched:
                if path in own:
                    continue
                owner = layout.file_problem.get(path)
                if owner is not None:
                    layout.warnings.append(
                        f"tour.yaml: {path} is listed under problems '{owner}' and '{problem['id']}'; "
                        f"kept under '{owner}'"
                    )
                    continue
                own.add(path)
                layout.listed.add(path)
                layout.file_problem[path] = problem["id"]
                kept[key].append(path)
    return kept["files"], kept["tests"]


def _place_unlisted(
    files: list[str], parts: list[dict[str, Any]], problems: list[dict[str, Any]], layout: Layout
) -> None:
    unlisted = [f for f in files if f not in layout.listed]
    if not unlisted:
        return
    by_part: dict[str, list[str]] = {}
    for path in unlisted:
        part = _part_for_folder(path, parts)
        if part is None:
            part = _other_part(parts)
        by_part.setdefault(part["id"], []).append(path)
    for part in parts:
        paths = by_part.get(part["id"])
        if not paths:
            continue
        problem_id = f"unplaced-{part['id']}"
        problems.append(
            {"id": problem_id, "part": part["id"], "title": "Not yet placed", "without": "", "fix": "",
             "files": paths, "tests": [], "placeholder": True}
        )  # fmt: skip
        part["problems"].append(problem_id)
        for path in paths:
            layout.warnings.append(
                f"tour.yaml: {path} is not listed under any problem "
                f"(shown under 'Not yet placed' in part '{part['id']}')"
            )


def _part_for_folder(path: str, parts: list[dict[str, Any]]) -> dict[str, Any] | None:
    best, best_len = None, -1
    for part in parts:
        for folder in part["folders"]:
            if path.startswith(folder) and len(folder) > best_len:
                best, best_len = part, len(folder)
    return best


def _other_part(parts: list[dict[str, Any]]) -> dict[str, Any]:
    for part in parts:
        if part["id"] == "other":
            return part
    part = {"id": "other", "name": "Other", "role": "Files that no part claims", "folders": [], "summary": "",
            "color": PALETTE[len(parts) % len(PALETTE)], "problems": []}  # fmt: skip
    parts.append(part)
    return part


# ---------------------------------------------------------------- auto mode


@dataclass
class AutoPart:
    id: str
    name: str
    folders: list[str]
    files: list[str]


def auto_parts(files: list[str], roles: dict[str, str]) -> list[AutoPart]:
    """Group files into parts by top-level folder (looking through src/); tests get their own part."""
    groups: dict[str, list[str]] = {}
    root_files: list[str] = []
    test_files: list[str] = []
    for path in files:
        if roles.get(path) == "test":
            test_files.append(path)
            continue
        key = _folder_key(path)
        if key is None:
            root_files.append(path)
        else:
            groups.setdefault(key, []).append(path)
    parts: list[AutoPart] = []
    used: set[str] = set()
    for key in sorted(groups):
        part_id = _unique_slug(key.rsplit("/", 1)[-1], used)
        parts.append(AutoPart(part_id, key.rsplit("/", 1)[-1], [key + "/"], groups[key]))
    if root_files:
        parts.append(AutoPart(_unique_slug("root", used), "Root", [], root_files))
    if test_files:
        parts.append(AutoPart(_unique_slug("tests", used), "Tests", [], test_files))
    return parts


def _folder_key(path: str) -> str | None:
    pieces = path.split("/")
    if len(pieces) == 1:
        return None
    if pieces[0] == "src":
        return None if len(pieces) == 2 else f"src/{pieces[1]}"
    return pieces[0]


def _unique_slug(name: str, used: set[str]) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "part"
    candidate, n = slug, 2
    while candidate in used:
        candidate, n = f"{slug}-{n}", n + 1
    used.add(candidate)
    return candidate


def auto_layout(files: list[str], roles: dict[str, str]) -> Layout:
    layout = Layout()
    for i, auto in enumerate(auto_parts(files, roles)):
        problem_id = f"{auto.id}-1"
        if auto.name == "Tests":
            title = "Test files"
        elif auto.name == "Root":
            title = "Files in the repo root"
        else:
            title = f"Files in {auto.folders[0]}"
        layout.parts.append(
            {"id": auto.id, "name": auto.name, "role": "", "folders": auto.folders, "summary": "",
             "color": PALETTE[i % len(PALETTE)], "problems": [problem_id]}
        )  # fmt: skip
        layout.problems.append(
            {"id": problem_id, "part": auto.id, "title": title, "without": "", "fix": "",
             "files": auto.files, "tests": [], "placeholder": True}
        )  # fmt: skip
        for path in auto.files:
            layout.file_problem[path] = problem_id
            layout.file_part[path] = auto.id
    return layout
