#!/usr/bin/env python3
"""Copy skills/repotour to src/repotour/skill so the packaged copy matches.

Usage: python scripts/sync_skill.py [--check]

--check exits 1 if the two folders differ, without changing anything.
"""

from __future__ import annotations

import filecmp
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "skills" / "repotour"
TARGET = ROOT / "src" / "repotour" / "skill"


def _files(base: Path) -> set[str]:
    return {
        p.relative_to(base).as_posix()
        for p in base.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }


def differs() -> bool:
    """Returns True when TARGET is missing or its files differ from SOURCE."""
    if not TARGET.is_dir():
        return True
    src, dst = _files(SOURCE), _files(TARGET)
    if src != dst:
        return True
    return any(not filecmp.cmp(SOURCE / f, TARGET / f, shallow=False) for f in src)


def sync() -> None:
    """Replaces TARGET with a fresh copy of SOURCE."""
    if TARGET.exists():
        shutil.rmtree(TARGET)
    shutil.copytree(SOURCE, TARGET, ignore=shutil.ignore_patterns("__pycache__"))


def main(argv: list[str]) -> int:
    if not SOURCE.is_dir():
        print(f"missing source folder: {SOURCE}", file=sys.stderr)
        return 2
    if "--check" in argv:
        if differs():
            print("src/repotour/skill is out of date; run scripts/sync_skill.py", file=sys.stderr)
            return 1
        print("skill copy is in sync")
        return 0
    sync()
    print(f"copied {SOURCE.relative_to(ROOT)} -> {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
