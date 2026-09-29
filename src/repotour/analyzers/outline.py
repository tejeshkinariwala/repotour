# Turns a flat list of top-level items plus "who references whom" into the nested outline:
# private items used by exactly one other item become its children, and every item gets `calls`.
# Used by both the Python and the JavaScript analyzers so the rules stay identical.
from __future__ import annotations

from repotour.analyzers.base import Item


def arrange(items: list[Item], refs: dict[str, set[str]]) -> list[Item]:
    """Nest private helpers under their single user and fill in `calls`.

    items: every top-level item in line order.
    refs: item name -> names of other top-level items it references.
    """
    by_name = {item.name: item for item in items}
    cleaned = {name: {r for r in refs.get(name, set()) if r in by_name and r != name} for name in by_name}
    parent = _find_parents(items, cleaned)
    for item in items:
        own_children = {n for n, p in parent.items() if p == item.name}
        targets = sorted(cleaned[item.name] - own_children, key=lambda n: by_name[n].line)
        item.calls = targets
    top: list[Item] = []
    for item in items:
        owner = parent.get(item.name)
        if owner is None:
            top.append(item)
        else:
            by_name[owner].children.append(item)
    return top


def _find_parents(items: list[Item], refs: dict[str, set[str]]) -> dict[str, str]:
    parent: dict[str, str] = {}
    for item in items:
        if not item.name.startswith("_"):
            continue
        users = [other.name for other in items if item.name in refs[other.name]]
        if len(users) != 1:
            continue
        if _is_ancestor(item.name, users[0], parent):
            continue  # would create a cycle
        parent[item.name] = users[0]
    return parent


def _is_ancestor(candidate: str, name: str, parent: dict[str, str]) -> bool:
    """True if `candidate` is `name` or one of its ancestors."""
    seen: set[str] = set()
    current: str | None = name
    while current is not None and current not in seen:
        if current == candidate:
            return True
        seen.add(current)
        current = parent.get(current)
    return False
