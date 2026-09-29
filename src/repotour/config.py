# Loads and validates the written content: .repotour/tour.yaml and .repotour/notes.yaml.
# Hard errors raise ConfigError (one line naming the file and the key). Softer problems
# (patterns that match nothing, missing notes ...) are found later, in build.py, as warnings.
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from repotour.roles import BUILTIN_ROLES

TOUR_FILE = ".repotour/tour.yaml"
NOTES_FILE = ".repotour/notes.yaml"


class ConfigError(Exception):
    """A problem in tour.yaml or notes.yaml that stops the build (exit code 2)."""


@dataclass
class Tour:
    project: dict[str, Any] = field(default_factory=dict)
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    roles: list[dict[str, str]] = field(default_factory=list)
    role_rules: list[tuple[str, list[str]]] = field(default_factory=list)
    parts: list[dict[str, Any]] = field(default_factory=list)
    problems: list[dict[str, Any]] = field(default_factory=list)
    stories: list[dict[str, Any]] = field(default_factory=list)
    guide: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)  # recommended fields that are empty


@dataclass
class Config:
    tour: Tour | None = None  # None: no tour.yaml, so auto mode
    notes: dict[str, dict[str, str]] = field(default_factory=dict)


def load_config(root: Path) -> Config:
    config = Config()
    tour_path = root / TOUR_FILE
    if tour_path.is_file():
        config.tour = _parse_tour(_read_yaml(tour_path, TOUR_FILE))
    notes_path = root / NOTES_FILE
    if notes_path.is_file():
        config.notes = _parse_notes(_read_yaml(notes_path, NOTES_FILE))
    return config


# ---------------------------------------------------------------- reading


def _read_yaml(path: Path, label: str) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as err:
        detail = " ".join(str(err).split())
        raise ConfigError(f"{label}: YAML syntax error: {detail}") from err
    except (OSError, UnicodeDecodeError) as err:
        raise ConfigError(f"{label}: cannot read file: {err}") from err


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    return [str(value)]


def _mapping_list(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = data.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise ConfigError(f"{TOUR_FILE}: {key}: expected a list")
    for i, entry in enumerate(value):
        if not isinstance(entry, dict):
            raise ConfigError(f"{TOUR_FILE}: {key}[{i}]: expected a mapping")
    return value


def _required(entry: dict[str, Any], key: str, where: str) -> str:
    value = _text(entry.get(key))
    if not value:
        raise ConfigError(f"{TOUR_FILE}: {where}.{key}: required")
    return value


# ---------------------------------------------------------------- tour.yaml


def _parse_tour(data: Any) -> Tour:
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ConfigError(f"{TOUR_FILE}: top level: expected a mapping")
    tour = Tour()
    project = data.get("project") or {}
    if not isinstance(project, dict):
        raise ConfigError(f"{TOUR_FILE}: project: expected a mapping")
    tour.project = project
    scan = data.get("scan") or {}
    if not isinstance(scan, dict):
        raise ConfigError(f"{TOUR_FILE}: scan: expected a mapping")
    tour.include = _string_list(scan.get("include"))
    tour.exclude = _string_list(scan.get("exclude"))
    tour.roles = _parse_roles(data)
    tour.role_rules = _parse_role_rules(
        data, {r["id"] for r in BUILTIN_ROLES} | {r["id"] for r in tour.roles}
    )
    tour.parts = _parse_parts(data, tour.warnings)
    part_ids = {p["id"] for p in tour.parts}
    tour.problems = _parse_problems(data, part_ids)
    tour.stories = _parse_stories(data)
    tour.guide = _parse_guide(data, {s["id"] for s in tour.stories}, part_ids)
    tour.warnings += _empty_field_warnings(data)
    return tour


# Fields the page needs to read well. Missing ones are warnings, not errors.
PLURAL = {"part": "parts", "problem": "problems", "story": "stories"}
RECOMMENDED = {"part": ("name", "summary"), "problem": ("title", "fix"), "story": ("title", "steps")}


def _empty_field_warnings(data: dict[str, Any]) -> list[str]:
    warnings = []
    for section, keys in RECOMMENDED.items():
        for entry in _mapping_list(data, PLURAL[section]):
            for key in keys:
                value = entry.get(key)
                if not (value if isinstance(value, list) else _text(value)):
                    warnings.append(f"tour.yaml: {section} '{_text(entry.get('id'))}': {key} is empty")
    return warnings


def _parse_roles(data: dict[str, Any]) -> list[dict[str, str]]:
    roles = []
    for i, entry in enumerate(_mapping_list(data, "roles")):
        where = f"roles[{i}]"
        role_id = _required(entry, "id", where)
        roles.append(
            {
                "id": role_id,
                "emoji": _text(entry.get("emoji")),
                "name": _text(entry.get("name")) or role_id,
                "meaning": _text(entry.get("meaning")),
            }
        )
    return roles


def _parse_role_rules(data: dict[str, Any], known: set[str]) -> list[tuple[str, list[str]]]:
    rules = []
    for i, entry in enumerate(_mapping_list(data, "role_rules")):
        role = _required(entry, "role", f"role_rules[{i}]")
        if role not in known:
            raise ConfigError(f"{TOUR_FILE}: role_rules[{i}].role: unknown role '{role}'")
        rules.append((role, _string_list(entry.get("match"))))
    return rules


# A part colour ends up inside a style attribute, so only plain colour values are allowed.
COLOR = re.compile(r"#[0-9a-fA-F]{3,8}|(rgb|rgba|hsl|hsla)\([0-9.,%\s]+\)|[a-zA-Z]+")


def _color(part_id: str, value: Any, warnings: list[str]) -> str | None:
    color = _text(value)
    if not color:
        return None
    if COLOR.fullmatch(color):
        return color
    warnings.append(f"tour.yaml: part '{part_id}': color '{color}' is not a plain colour; using the palette")
    return None


def _parse_parts(data: dict[str, Any], warnings: list[str]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i, entry in enumerate(_mapping_list(data, "parts")):
        part_id = _required(entry, "id", f"parts[{i}]")
        if part_id in seen:
            raise ConfigError(f"{TOUR_FILE}: parts[{i}].id: duplicate part id '{part_id}'")
        seen.add(part_id)
        folders = [f if f.endswith("/") else f + "/" for f in _string_list(entry.get("folders"))]
        parts.append(
            {
                "id": part_id,
                "name": _text(entry.get("name")) or part_id,
                "role": _text(entry.get("role")),
                "folders": folders,
                "summary": _text(entry.get("summary")),
                "color": _color(part_id, entry.get("color"), warnings),
            }
        )
    return parts


def _parse_problems(data: dict[str, Any], part_ids: set[str]) -> list[dict[str, Any]]:
    problems: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i, entry in enumerate(_mapping_list(data, "problems")):
        where = f"problems[{i}]"
        problem_id = _required(entry, "id", where)
        if problem_id in seen:
            raise ConfigError(f"{TOUR_FILE}: {where}.id: duplicate problem id '{problem_id}'")
        seen.add(problem_id)
        part = _required(entry, "part", where)
        if part not in part_ids:
            raise ConfigError(f"{TOUR_FILE}: {where}.part: unknown part '{part}' (problem {problem_id})")
        problems.append(
            {
                "id": problem_id,
                "part": part,
                "title": _text(entry.get("title")),
                "without": _text(entry.get("without")),
                "fix": _text(entry.get("fix")),
                "files": _string_list(entry.get("files")),
                "tests": _string_list(entry.get("tests")),
            }
        )
    return problems


def _parse_stories(data: dict[str, Any]) -> list[dict[str, Any]]:
    stories: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i, entry in enumerate(_mapping_list(data, "stories")):
        where = f"stories[{i}]"
        story_id = _required(entry, "id", where)
        if story_id in seen:
            raise ConfigError(f"{TOUR_FILE}: {where}.id: duplicate story id '{story_id}'")
        seen.add(story_id)
        stories.append(
            {
                "id": story_id,
                "act": _text(entry.get("act")),
                "title": _text(entry.get("title")),
                "command": _text(entry.get("command")),
                "summary": _text(entry.get("summary")),
                "steps": _parse_steps(entry.get("steps"), where),
            }
        )
    return stories


def _parse_steps(value: Any, where: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ConfigError(f"{TOUR_FILE}: {where}.steps: expected a list")
    steps = []
    for j, step in enumerate(value):
        if not isinstance(step, dict):
            raise ConfigError(f"{TOUR_FILE}: {where}.steps[{j}]: expected a mapping")
        steps.append({"text": _text(step.get("text")), "files": _string_list(step.get("files"))})
    return steps


def _parse_guide(data: dict[str, Any], story_ids: set[str], part_ids: set[str]) -> list[dict[str, Any]]:
    guide = []
    for i, entry in enumerate(_mapping_list(data, "guide")):
        story = _text(entry.get("story")) or None
        part = _text(entry.get("part")) or None
        if story is not None and story not in story_ids:
            raise ConfigError(f"{TOUR_FILE}: guide[{i}].story: unknown story '{story}'")
        if part is not None and part not in part_ids:
            raise ConfigError(f"{TOUR_FILE}: guide[{i}].part: unknown part '{part}'")
        guide.append({"text": _text(entry.get("text")), "story": story, "part": part})
    return guide


# ---------------------------------------------------------------- notes.yaml


def _parse_notes(data: Any) -> dict[str, dict[str, str]]:
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"{NOTES_FILE}: top level: expected a mapping of file paths")
    notes: dict[str, dict[str, str]] = {}
    for path, entries in data.items():
        if entries is None:
            entries = {}
        if not isinstance(entries, dict):
            raise ConfigError(f"{NOTES_FILE}: {path}: expected a mapping of item names to notes")
        notes[str(path)] = {str(name): _text(note) for name, note in entries.items()}
    return notes
