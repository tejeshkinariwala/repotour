# Applies notes.yaml to the parsed files: one-line notes on outline items, plus the `_file` purpose.
# Also produces the warnings for missing notes and notes whose target no longer exists.
from __future__ import annotations

from collections.abc import Iterator

from repotour.analyzers.base import FileFacts, Item, Method
from repotour.repo import RepoFacts

FILE_KEY = "_file"


def outline_keys(items: list[Item]) -> Iterator[tuple[str, Item | Method]]:
    """Every noteable thing in an outline, in reading order: items, their methods, their children."""
    for item in items:
        yield item.name, item
        for method in item.methods:
            yield f"{item.name}.{method.name}", method
        yield from outline_keys(item.children)


def purpose_of(facts: FileFacts, notes: dict[str, str] | None) -> str:
    if notes and notes.get(FILE_KEY):
        return notes[FILE_KEY]
    return facts.header


def apply_notes(repo: RepoFacts, notes: dict[str, dict[str, str]]) -> list[str]:
    """Attach notes to outline items (in place) and return the warnings."""
    warnings: list[str] = []
    for path, entries in notes.items():
        facts = repo.facts.get(path)
        if facts is None:
            if any(text for text in entries.values()):
                warnings.append(f"notes.yaml: {path}: file has notes but is not in the repo")
            continue
        if facts.items is None:
            if any(key != FILE_KEY and text for key, text in entries.items()):
                warnings.append(f"notes.yaml: {path}: file has notes but is not outlined")
            continue
        warnings.extend(_apply_to_file(path, facts.items, entries))
    return warnings


def _apply_to_file(path: str, items: list[Item], entries: dict[str, str]) -> list[str]:
    warnings: list[str] = []
    known = dict(outline_keys(items))
    wrote_any = any(text for key, text in entries.items() if key != FILE_KEY)
    for key, target in known.items():
        text = entries.get(key)
        if text:
            target.note = text
        elif wrote_any:
            warnings.append(f"notes.yaml: {path}: missing note for '{key}'")
    for key in entries:
        if key != FILE_KEY and key not in known:
            warnings.append(f"notes.yaml: {path}: note for '{key}' but no such item exists any more")
    return warnings


def coverage_warnings(repo: RepoFacts, notes: dict[str, dict[str, str]]) -> list[str]:
    """Written mode: warn about non-test files with no notes entry or no purpose line."""
    warnings = []
    for path in repo.files:
        if repo.roles[path] == "test":
            continue
        items = repo.facts[path].items
        if items and path not in notes:
            count = sum(1 for _ in outline_keys(items))
            warnings.append(f"notes.yaml: no notes for {path} ({count} items)")
        if not purpose_of(repo.facts[path], notes.get(path)):
            warnings.append(f"{path}: no purpose line (add _file in notes.yaml or a header comment)")
    return warnings
