# `repotour install-skill`: copies the packaged Claude Code skill into a project or the user folder.
from __future__ import annotations

import shutil
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # only for the annotation; the module path differs across Python versions
    from importlib.resources.abc import Traversable


class InstallError(Exception):
    """The skill could not be installed."""


def install_skill(project: Path | None, force: bool = False) -> Path:
    """Copy the skill to PROJECT/.claude/skills/repotour (or the user folder). Returns the target."""
    source = resources.files("repotour").joinpath("skill")
    if not source.is_dir() or not source.joinpath("SKILL.md").is_file():
        raise InstallError("the skill files are missing from this install of repotour (no skill/SKILL.md)")
    base = Path.home() if project is None else project
    target = base / ".claude" / "skills" / "repotour"
    if target.is_symlink() or target.exists():
        if not force:
            raise InstallError(f"{target}: already exists (use --force to replace it)")
        if target.is_symlink() or target.is_file():
            target.unlink()  # remove the link itself, never what it points to
        else:
            shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.mkdir()
    _copy_tree(source, target)
    return target


def _copy_tree(source: Traversable, target: Path) -> None:
    for entry in source.iterdir():
        if entry.name == "__pycache__":
            continue
        destination = target / entry.name
        if entry.is_dir():
            destination.mkdir()
            _copy_tree(entry, destination)
        else:
            destination.write_bytes(entry.read_bytes())
