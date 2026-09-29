# Tests for role assignment: user rules first, then the default rules, first match wins.
from repotour.roles import assign_role, merge_roles


def test_default_rules_in_order():
    assert assign_role("tests/x.py", []) == "test"
    assert assign_role("src/api/settings.py", []) == "config"
    assert assign_role("src/pkg/__init__.py", []) == "helper"
    assert assign_role("src/__main__.py", []) == "conductor"
    assert assign_role("web/Widget.tsx", []) == "face"
    assert assign_role("src/auth_check.py", []) == "guard"
    assert assign_role("src/user_store.py", []) == "storekeeper"
    assert assign_role("src/http_client.py", []) == "courier"
    assert assign_role("src/metrics.py", []) == "analyst"
    assert assign_role("src/types.ts", []) == "rulebook"
    assert assign_role("src/engine.py", []) == "worker"


def test_patterns_are_case_insensitive():
    assert assign_role("SRC/Main.PY", []) == "conductor"


def test_user_rules_win():
    assert assign_role("src/engine.py", [("conductor", ["src/engine.py"])]) == "conductor"


def test_index_is_helper_only_when_it_just_reexports():
    assert assign_role("src/index.ts", [], reexport_only=True) == "helper"
    assert assign_role("src/index.ts", [], reexport_only=False) == "worker"


def test_merge_roles_adds_and_overrides():
    roles = merge_roles(
        [
            {"id": "guard", "emoji": "X", "name": "G", "meaning": "m"},
            {"id": "new", "emoji": "N", "name": "New", "meaning": "n"},
        ]
    )
    ids = [r["id"] for r in roles]
    assert ids.count("guard") == 1 and ids[-1] == "new"
    assert next(r for r in roles if r["id"] == "guard")["emoji"] == "X"
