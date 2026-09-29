# The built-in roles (emoji categories) and the default rules that pick one for each file.
# User rules from tour.yaml are checked first; the first matching rule wins.
from __future__ import annotations

from dataclasses import dataclass

from repotour.globs import matches_any

BUILTIN_ROLES: list[dict[str, str]] = [
    {"id": "conductor", "emoji": "🎬", "name": "Conductor",
     "meaning": "Starts things and calls other files in order: entry points, CLIs, servers, scripts, "
                "build steps."},
    {"id": "rulebook", "emoji": "📐", "name": "Rulebook",
     "meaning": "Defines what things must look like: types, schemas, interfaces, base classes, "
                "constants, registries. Does little work itself."},
    {"id": "worker", "emoji": "⚙️", "name": "Worker",
     "meaning": "Does the actual work: the core logic, algorithms and transformations."},
    {"id": "guard", "emoji": "🛡️", "name": "Guard",
     "meaning": "Checks something and refuses or stops when it is wrong: validation, auth, "
                "permissions, limits."},
    {"id": "storekeeper", "emoji": "📦", "name": "Storekeeper",
     "meaning": "Saves and loads data: databases, caches, files, queues, migrations."},
    {"id": "courier", "emoji": "🔌", "name": "Courier",
     "meaning": "Talks to the outside world: HTTP clients, API adapters, SDK wrappers, messaging."},
    {"id": "analyst", "emoji": "🔍", "name": "Analyst",
     "meaning": "Measures and reports: metrics, logging, statistics, reports, charts."},
    {"id": "face", "emoji": "🖼️", "name": "Face",
     "meaning": "What a user sees: UI components, pages, views, templates, styles."},
    {"id": "config", "emoji": "🗂️", "name": "Settings",
     "meaning": "A file of settings or records that code reads."},
    {"id": "helper", "emoji": "🧩", "name": "Helper",
     "meaning": "Small shared utilities and package markers."},
    {"id": "test", "emoji": "🧪", "name": "Test",
     "meaning": "Automated test that checks other files still behave as before."},
]  # fmt: skip


@dataclass(frozen=True)
class Rule:
    role: str
    patterns: tuple[str, ...]
    only_if_reexport: bool = False  # the pattern counts only when the file just re-exports


DEFAULT_RULES: list[Rule] = [
    Rule("test", ("tests/**", "test/**", "**/__tests__/**", "**/test_*.py", "**/*_test.py", "**/*.test.*",
                  "**/*.spec.*", "**/conftest.py")),
    Rule("config", ("*.yaml", "*.yml", "*.toml", "*.json", "*.ini", "*.cfg", "**/*.config.{js,ts,mjs,cjs}",
                    "**/settings.py", "**/config.py", "**/config/**")),
    Rule("helper", ("**/__init__.py",)),
    Rule("helper", ("**/index.{js,ts}",), only_if_reexport=True),
    Rule("helper", ("**/util*", "**/helper*", "**/common*", "**/_util*")),
    Rule("conductor", ("**/__main__.py", "**/main.{py,js,ts}", "**/cli*.{py,js,ts}", "**/app.{py,js,ts}",
                       "**/server.{py,js,ts}", "**/manage.py", "bin/**", "scripts/**", "*.sh", "**/*.sh",
                       "**/commands/**")),
    Rule("face", ("**/*.{jsx,tsx}", "**/components/**", "**/pages/**", "**/views/**", "**/templates/**",
                  "**/ui/**")),
    Rule("guard", ("**/*valid*", "**/*auth*", "**/*guard*", "**/*permission*", "**/*policy*", "**/*check*",
                   "**/middleware*")),
    Rule("storekeeper", ("**/*store*", "**/*cache*", "**/*db*", "**/*database*", "**/*repo*", "**/*storage*",
                         "**/models/**", "**/migrations/**", "**/*persist*")),
    Rule("courier", ("**/*client*", "**/*api*", "**/*http*", "**/*adapter*", "**/*integration*",
                     "**/*webhook*", "**/*sdk*")),
    Rule("analyst", ("**/*report*", "**/*metric*", "**/*stat*", "**/*log*", "**/*analytic*",
                     "**/*telemetry*")),
    Rule("rulebook", ("**/*types*", "**/*schema*", "**/*model*", "**/*interface*", "**/*const*", "**/*enum*",
                      "**/*base*", "**/*registry*", "**/*.d.ts", "**/*.pyi")),
]  # fmt: skip

FALLBACK_ROLE = "worker"


def merge_roles(extra: list[dict[str, str]]) -> list[dict[str, str]]:
    """Built-in roles plus the user's roles; a user role with a known id replaces that role."""
    roles = {r["id"]: dict(r) for r in BUILTIN_ROLES}
    for role in extra:
        roles[role["id"]] = role
    return list(roles.values())


def assign_role(path: str, user_rules: list[tuple[str, list[str]]], reexport_only: bool = False) -> str:
    """Pick a role id for one file. user_rules is [(role_id, patterns)] from tour.yaml."""
    for role_id, patterns in user_rules:
        if matches_any(path, patterns, ignore_case=True):
            return role_id
    for rule in DEFAULT_RULES:
        if rule.only_if_reexport and not reexport_only:
            continue
        if matches_any(path, list(rule.patterns), ignore_case=True):
            return rule.role
    return FALLBACK_ROLE
