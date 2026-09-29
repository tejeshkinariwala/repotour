# Collects the facts about a repo: scans the file list, parses every file once with the right
# analyzer, assigns roles and works out which files import which (used_by).
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from repotour.analyzers import analyze_file, language_for
from repotour.analyzers.base import Context, FileFacts, count_lines
from repotour.config import Config
from repotour.roles import assign_role
from repotour.scan import read_text, scan_files


@dataclass
class RepoFacts:
    root: Path
    files: list[str] = field(default_factory=list)  # sorted, repo-relative POSIX paths
    facts: dict[str, FileFacts] = field(default_factory=dict)
    roles: dict[str, str] = field(default_factory=dict)  # path -> role id
    used_by: dict[str, list[str]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def collect_facts(root: Path, config: Config) -> RepoFacts:
    """Scan and analyze the repo. Each file is read and parsed exactly once."""
    tour = config.tour
    scanned = scan_files(root, tour.include if tour else None, tour.exclude if tour else None)
    repo = RepoFacts(root=root, warnings=list(scanned.warnings))
    ctx = Context(root=root, files=frozenset(scanned.files))
    user_rules = tour.role_rules if tour else []
    for path in scanned.files:
        text = read_text(root, path)
        if text is None:
            continue  # binary file
        facts = _analyze(path, text, ctx)
        repo.files.append(path)
        repo.facts[path] = facts
        repo.warnings.extend(facts.warnings)
        repo.roles[path] = assign_role(path, user_rules, facts.reexport_only)
    known = set(repo.files)
    used_by: dict[str, list[str]] = {}
    for path in repo.files:
        for target in repo.facts[path].imports:
            if target in known:
                used_by.setdefault(target, []).append(path)
    repo.used_by = {target: sorted(users) for target, users in used_by.items()}
    return repo


def _analyze(path: str, text: str, ctx: Context) -> FileFacts:
    try:
        return analyze_file(path, text, ctx)
    except Exception as err:  # an analyzer bug must not stop the whole tour
        facts = FileFacts(path=path, lang=language_for(path), lines=count_lines(text))
        facts.warnings.append(f"{path}: analyzer failed ({type(err).__name__}), listed without an outline")
        return facts
