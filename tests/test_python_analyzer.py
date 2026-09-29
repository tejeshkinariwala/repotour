# Tests for the Python analyzer, mostly on the py_app fixture and small snippets.
from conftest import analyze_snippet

from repotour.analyzers.base import Item


def item_names(items: list[Item]) -> list[str]:
    return [i.name for i in items]


def test_docstring_first_paragraph_is_header():
    facts = analyze_snippet("m.py", '"""First para.\n\nSecond para."""\n')
    assert facts.header == "First para."


def test_comment_header_after_shebang_and_encoding():
    facts = analyze_snippet(
        "m.py", "#!/usr/bin/env python\n# -*- coding: utf-8 -*-\n# Does a thing.\n# More.\nx = 1\n"
    )
    assert facts.header == "Does a thing. More."


def test_class_methods_and_signatures():
    src = "class A(Base, Other):\n    def go(self, x: int, y='a'): ...\n    async def wait(self): ...\n"
    facts = analyze_snippet("m.py", src)
    (item,) = facts.items
    assert item.kind == "class" and item.signature == "class A(Base, Other)"
    assert [(m.name, m.signature) for m in item.methods] == [
        ("go", "go(self, x: int, y='a')"),
        ("wait", "wait(self)"),
    ]


def test_long_annotations_are_dropped():
    long = "dict[str, dict[str, list[tuple[int, str]]]]"
    facts = analyze_snippet("m.py", f"def f(a: {long}, b: int): ...\n")
    assert facts.items[0].signature == "f(a, b: int)"


def test_private_helper_used_once_becomes_child():
    src = "def _h(): ...\ndef main():\n    return _h()\n"
    facts = analyze_snippet("m.py", src)
    assert item_names(facts.items) == ["main"]
    assert item_names(facts.items[0].children) == ["_h"]
    assert facts.items[0].calls == []  # children are not listed as calls


def test_private_helper_used_twice_stays_top_level():
    src = "def _h(): ...\ndef a():\n    _h()\ndef b():\n    _h()\n"
    facts = analyze_snippet("m.py", src)
    assert item_names(facts.items) == ["_h", "a", "b"]
    assert facts.items[1].calls == ["_h"]


def test_reference_cycle_is_broken():
    src = "def _a():\n    _b()\ndef _b():\n    _a()\n"
    facts = analyze_snippet("m.py", src)
    assert len(facts.items) == 1  # one of them nests under the other, none lost
    assert len(facts.items[0].children) == 1


def test_function_table_is_an_item_and_owns_private_handlers():
    src = "def _one(): ...\ndef two(): ...\nTABLE = {'a': _one, 'b': two}\n"
    facts = analyze_snippet("m.py", src)
    assert item_names(facts.items) == ["two", "TABLE"]
    table = facts.items[1]
    assert table.kind == "table" and table.calls == ["two"]
    assert item_names(table.children) == ["_one"]


def test_dict_without_functions_is_a_constant_not_a_table():
    facts = analyze_snippet("m.py", "LIMITS = {'a': 1}\nmax_size = 3\n")
    assert facts.items == []
    assert facts.consts == ["LIMITS"]


def test_exported_respects_underscore_and_dunder_all():
    facts = analyze_snippet("m.py", "__all__ = ['a']\ndef a(): ...\ndef b(): ...\n")
    assert {i.name: i.exported for i in facts.items} == {"a": True, "b": False}
    facts = analyze_snippet(
        "m.py", "def a(): ...\ndef _b():\n    pass\ndef c():\n    _b()\ndef d():\n    _b()\n"
    )
    assert {i.name: i.exported for i in facts.items}["_b"] is False


def test_syntax_error_lists_file_without_outline():
    facts = analyze_snippet("m.py", "def oops(:\n")
    assert facts.items is None
    assert "syntax error" in facts.warnings[0] and "m.py" in facts.warnings[0]


def test_imports_absolute_relative_and_libs():
    files = (
        "pkg/__init__.py",
        "pkg/a.py",
        "pkg/sub/__init__.py",
        "pkg/sub/b.py",
        "src/tool/__init__.py",
        "src/tool/c.py",
    )
    src = (
        "import os, json\nimport pkg.a\nfrom pkg import sub\nfrom pkg.sub import b as bee, thing\n"
        "from .a import A\nfrom . import a as sibling\nfrom tool import c\n"
        "from __future__ import annotations\n"
        "def f():\n    import yaml\n"
    )
    facts = analyze_snippet("pkg/x.py", src, files)
    assert set(facts.imports) == {"pkg/a.py", "pkg/sub/__init__.py", "pkg/sub/b.py", "src/tool/c.py"}
    assert facts.imports["pkg/a.py"] == ["A"]
    assert facts.imports["pkg/sub/b.py"] == []
    assert facts.imports["pkg/sub/__init__.py"] == ["thing"]
    assert facts.libs == ["json", "os", "yaml"]


def test_py_app_fixture_outline(py_app):
    from repotour.config import Config
    from repotour.repo import collect_facts

    repo = collect_facts(py_app, Config())
    reports = repo.facts["acme_app/reports.py"]
    names = item_names(reports.items)
    assert "_format_line" not in names  # nested under run_report
    run_report = next(i for i in reports.items if i.name == "run_report")
    assert item_names(run_report.children) == ["_format_line"]
    assert repo.facts["acme_app/commands.py"].items[1].kind == "table"
    assert repo.facts["acme_app/broken.py"].items is None
    assert repo.roles["acme_app/__main__.py"] == "conductor"
    assert repo.roles["tests/test_reports.py"] == "test"
    assert repo.roles["acme_app/settings.yaml"] == "config"
    assert repo.used_by["acme_app/models.py"][0] == "acme_app/__init__.py"
    assert any("broken.py" in w for w in repo.warnings)
