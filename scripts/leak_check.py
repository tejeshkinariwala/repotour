#!/usr/bin/env python3
"""Scan tracked and staged files for terms from a private denylist.

The denylist is a text file, one term per line (blank lines and lines starting
with # are ignored). It is read from $REPOTOUR_DENYLIST or
~/.config/repotour/denylist.txt and is never stored in the repo.

Matching is case-insensitive and whole-word. Each hit prints as file:line:term.
Exit code 1 if any hit, 0 otherwise. If no denylist exists, prints a notice and
exits 0.

Usage:
    python scripts/leak_check.py                 run the check
    python scripts/leak_check.py --install-hook  install as .git/hooks/pre-commit
"""

from __future__ import annotations

import os
import re
import stat
import subprocess
import sys
from pathlib import Path

HOOK = """#!/bin/sh
# Installed by scripts/leak_check.py --install-hook
exec python3 "$(git rev-parse --show-toplevel)/scripts/leak_check.py"
"""


def repo_root() -> Path:
    out = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False)
    if out.returncode == 0 and out.stdout.strip():
        return Path(out.stdout.strip())
    return Path(__file__).resolve().parent.parent


def denylist_path() -> Path:
    env = os.environ.get("REPOTOUR_DENYLIST")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".config" / "repotour" / "denylist.txt"


def load_terms(path: Path) -> list[str]:
    terms = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            terms.append(line)
    return terms


def git_files(root: Path) -> list[str]:
    """Tracked files, staged files, and untracked files that are not ignored."""
    names: set[str] = set()
    for args in (
        ["ls-files"],
        ["diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        ["ls-files", "--others", "--exclude-standard"],
    ):
        out = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)
        if out.returncode == 0:
            names.update(n for n in out.stdout.splitlines() if n)
    return sorted(names)


def compile_terms(terms: list[str]) -> list[tuple[str, re.Pattern[str]]]:
    return [(t, re.compile(r"(?<!\w)" + re.escape(t) + r"(?!\w)", re.IGNORECASE)) for t in terms]


def scan(root: Path, terms: list[str]) -> list[tuple[str, int, str]]:
    patterns = compile_terms(terms)
    hits: list[tuple[str, int, str]] = []
    for name in git_files(root):
        path = root / name
        if not path.is_file():
            continue
        data = path.read_bytes()
        if b"\0" in data[:8192]:
            continue
        text = data.decode("utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            for term, pat in patterns:
                if pat.search(line):
                    hits.append((name, lineno, term))
    return hits


def install_hook(root: Path) -> int:
    hooks = root / ".git" / "hooks"
    if not hooks.is_dir():
        print("no .git/hooks folder found; run from a git repository", file=sys.stderr)
        return 2
    target = hooks / "pre-commit"
    if target.exists() and "leak_check.py" not in target.read_text(errors="replace"):
        print(f"{target} already exists and is not ours; not overwriting", file=sys.stderr)
        return 2
    target.write_text(HOOK)
    target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"installed {target}")
    return 0


def main(argv: list[str]) -> int:
    root = repo_root()
    if "--install-hook" in argv:
        return install_hook(root)
    path = denylist_path()
    if not path.is_file():
        print(f"leak_check: no denylist at {path}; skipping.")
        return 0
    terms = load_terms(path)
    if not terms:
        print("leak_check: denylist is empty; skipping.")
        return 0
    hits = scan(root, terms)
    for name, lineno, term in hits:
        print(f"{name}:{lineno}:{term}")
    if hits:
        print(f"leak_check: {len(hits)} hit(s).", file=sys.stderr)
        return 1
    print("leak_check: clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
