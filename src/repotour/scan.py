# Finds the files that belong in the tour: walks the repo (or asks git), applies the built-in
# skips, the default suffix list and the include/exclude patterns from tour.yaml.
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from repotour.analyzers import DEFAULT_SUFFIXES
from repotour.globs import matches_any

# Skipped at any depth, always (also when git lists the files).
ALWAYS_SKIP_DIRS = frozenset(
    {
        ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__", ".tox", ".repotour",
        ".next", ".nuxt",
    }
)  # fmt: skip
# Also skipped when walking a folder that is not a git repo. In a git repo, git decides.
NON_GIT_SKIP_DIRS = frozenset({"build", "dist", "target", "vendor", "env", "coverage"})

LOCKFILES = frozenset({"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "uv.lock"})
MAX_BYTES = 1_000_000
DEFAULT_INCLUDE = ["**/*"]


@dataclass
class ScanResult:
    files: list[str] = field(default_factory=list)  # repo-relative POSIX paths, sorted
    warnings: list[str] = field(default_factory=list)


def scan_files(root: Path, include: list[str] | None = None, exclude: list[str] | None = None) -> ScanResult:
    """List the tour's files under root. include/exclude come from tour.yaml (scan section)."""
    include = include or DEFAULT_INCLUDE
    exclude = exclude or []
    default_include = include == DEFAULT_INCLUDE
    result = ScanResult()
    for rel in sorted(_candidate_paths(root)):
        if not _wanted(rel, include, exclude, default_include):
            continue
        if (root / rel).is_symlink():  # a link could point outside the repo; never read through it
            result.warnings.append(f"{rel}: skipped, is a symbolic link")
            continue
        try:
            size = (root / rel).stat().st_size
        except OSError:
            continue
        if size > MAX_BYTES:
            result.warnings.append(f"{rel}: skipped, larger than 1 MB")
            continue
        result.files.append(rel)
    return result


def _wanted(rel: str, include: list[str], exclude: list[str], default_include: bool) -> bool:
    name = rel.rsplit("/", 1)[-1]
    if name in LOCKFILES or name.endswith((".min.js", ".map")):
        return False
    if exclude and matches_any(rel, exclude):
        return False
    if default_include:
        return os.path.splitext(name)[1].lower() in DEFAULT_SUFFIXES
    return matches_any(rel, include)


def _is_skipped_dir(name: str, extra: frozenset[str] = frozenset()) -> bool:
    return name in ALWAYS_SKIP_DIRS or name in extra or name.endswith("_cache")


def _skipped_dir(rel: str, extra: frozenset[str] = frozenset()) -> bool:
    return any(_is_skipped_dir(part, extra) for part in rel.split("/")[:-1])


def _candidate_paths(root: Path) -> list[str]:
    from_git = _git_paths(root) if (root / ".git").exists() else None
    if from_git is not None:
        return [p for p in from_git if not _skipped_dir(p)]
    return _walk_paths(root)


def _git_paths(root: Path) -> list[str] | None:
    if shutil.which("git") is None:
        return None
    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=root, capture_output=True, check=True, timeout=60,
        )  # fmt: skip
    except (subprocess.SubprocessError, OSError):
        return None
    names = [n for n in out.stdout.decode("utf-8", "replace").split("\0") if n]
    return [n for n in names if (root / n).is_file()]


def _walk_paths(root: Path) -> list[str]:
    paths: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not _is_skipped_dir(d, NON_GIT_SKIP_DIRS)]
        base = os.path.relpath(dirpath, root)
        for name in filenames:
            rel = name if base == "." else f"{base}/{name}"
            paths.append(rel.replace(os.sep, "/"))
    return paths


def read_text(root: Path, rel: str) -> str | None:
    """Read a file as text; None if it looks binary."""
    try:
        data = (root / rel).read_bytes()
    except OSError:
        return None
    if b"\0" in data[:8192]:
        return None
    return data.decode("utf-8", "replace")
