# Shared types for analyzers: the Analyzer protocol, the facts an analyzer returns for one file,
# and the Context that lets an analyzer resolve imports to other files in the repo.
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Protocol

MAX_HEADER = 300


@dataclass
class Method:
    name: str
    line: int
    signature: str
    note: str | None = None


@dataclass
class Item:
    name: str
    kind: str  # "function" | "class" | "table" | "type" | "const"
    line: int
    signature: str
    exported: bool
    methods: list[Method] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)
    children: list[Item] = field(default_factory=list)
    note: str | None = None


@dataclass
class FileFacts:
    path: str
    lang: str
    lines: int
    header: str = ""
    items: list[Item] | None = None  # None: this file type has no outline
    consts: list[str] = field(default_factory=list)
    imports: dict[str, list[str]] = field(default_factory=dict)  # in-repo file -> imported names
    libs: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    reexport_only: bool = False  # JS/TS: the file only re-exports from other files


@dataclass
class Context:
    """What an analyzer may know about the repo: its root and the set of files in the tour."""

    root: Path
    files: frozenset[str]
    cache: dict[str, object] = field(default_factory=dict)  # per-run scratch space for analyzers

    @cached_property
    def dirs(self) -> frozenset[str]:
        """Every folder that holds at least one file of the tour (repo root is the empty string)."""
        found: set[str] = {""}
        for path in self.files:
            parts = path.split("/")[:-1]
            for i in range(1, len(parts) + 1):
                found.add("/".join(parts[:i]))
        return frozenset(found)

    @cached_property
    def python_roots(self) -> list[str]:
        """Folders that absolute Python imports may start from: the repo root, src/, and any
        top-level folder that holds a root package (folder/pkg/__init__.py)."""
        roots = ["", "src"]
        for path in sorted(self.files):
            parts = path.split("/")
            if len(parts) == 3 and parts[2] == "__init__.py" and parts[0] not in roots:
                roots.append(parts[0])
        return roots

    def read_repo_file(self, rel: str) -> str | None:
        try:
            return (self.root / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None


class Analyzer(Protocol):
    def analyze(self, path: str, text: str, ctx: Context) -> FileFacts:
        """Parse one file's text once and return its facts."""
        ...


def one_line(text: str, limit: int = MAX_HEADER) -> str:
    """Collapse whitespace into a single line and trim it to the limit."""
    line = re.sub(r"\s+", " ", text).strip()
    if len(line) > limit:
        line = line[: limit - 1].rstrip() + "…"
    return line


def count_lines(text: str) -> int:
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def add_import(imports: dict[str, list[str]], target: str, names: list[str]) -> None:
    """Record an import of `target`, merging imported names without duplicates."""
    have = imports.setdefault(target, [])
    for name in names:
        if name not in have:
            have.append(name)
