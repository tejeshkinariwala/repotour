# Regression tests for analyzer fixes: shared outline, Python overloads/conditionals/headers,
# TS/JS value exports, overloads, signatures, parse misses, headers, tsconfig scoping, languages.
import json
from pathlib import Path

from conftest import analyze_snippet

from repotour import analyzers
from repotour.analyzers.base import Context
from repotour.analyzers.jsresolve import JsResolver
from repotour.build import build_data
from repotour.cli import main


def names(items):
    return [i.name for i in items]


def by_name(facts):
    return {i.name: i for i in facts.items}


# ---------------------------------------------------------------- 1. one outline for scan and build


def test_scan_json_and_build_share_one_outline(tmp_path, capsys):
    (tmp_path / "m.py").write_text(
        "def top():\n    return _helper()\n\n\ndef _helper():\n    return 1\n\n\n"
        "class K:\n    def run(self):\n        return _ctx()\n\n\ndef _ctx():\n    return 2\n"
    )
    assert main(["scan", str(tmp_path), "--json"]) == 0
    scanned = json.loads(capsys.readouterr().out)["files"][0]["outline"]
    built = build_data(tmp_path)["files"]["m.py"]["outline"]
    assert scanned == built
    top = {i["name"]: i for i in built["items"]}
    assert [c["name"] for c in top["top"]["children"]] == ["_helper"]  # SPEC 5.3: used by one item
    assert [c["name"] for c in top["K"]["children"]] == ["_ctx"]  # references count in method bodies


def test_private_item_used_by_two_items_stays_top_level():
    src = "def a():\n    _h()\n\n\ndef b():\n    _h()\n\n\ndef _h():\n    pass\n"
    facts = analyze_snippet("m.py", src)
    assert names(facts.items) == ["a", "b", "_h"]


# ---------------------------------------------------------------- 2. Python overloads


def test_python_overloads_collapse_to_implementation():
    src = (
        "from typing import overload\nimport typing\n\n"
        "@overload\ndef f(a: int) -> int: ...\n@typing.overload\ndef f(a: str) -> str: ...\n"
        "def f(a, b=None):\n    return a\n\n\n"
        "@overload\ndef g(a: int) -> int: ...\n@overload\ndef g(a: str, b: int) -> str: ...\n\n\n"
        "class C:\n    @overload\n    def m(self, a: int) -> int: ...\n"
        "    @overload\n    def m(self, a: str) -> str: ...\n    def m(self, a):\n        return a\n"
    )
    facts = analyze_snippet("m.py", src)
    items = by_name(facts)
    assert names(facts.items) == ["f", "g", "C"]
    assert items["f"].signature == "f(a, b=None)"
    assert items["g"].signature == "g(a: int)"  # no implementation: first definition
    assert [(m.name, m.signature) for m in items["C"].methods] == [("m", "m(self, a)")]


# ---------------------------------------------------------------- 3. Python conditional definitions


def test_python_conditional_definitions_are_outlined_first_wins():
    src = (
        "import sys\n\nif sys.platform == 'win32':\n    def reg(host):\n        return 1\n"
        "    class W:\n        pass\nelse:\n    def reg(host, extra):\n        return 2\n\n"
        "try:\n    import x\n    def fast():\n        pass\nexcept ImportError:\n    def fast():\n"
        "        pass\n    def slow():\n        pass\n"
    )
    facts = analyze_snippet("m.py", src)
    assert names(facts.items) == ["reg", "W", "fast", "slow"]
    assert by_name(facts)["reg"].signature == "reg(host)"


# ---------------------------------------------------------------- 4. Python header


def test_python_header_skips_rest_titles_art_and_fields():
    title = (
        '"""\nrequests.hooks\n~~~~~~~~~~~~~~\n\nThis module provides hooks.\n\n'
        ':copyright: (c) x\n:license: Apache2\n"""\n'
    )
    assert analyze_snippet("m.py", title).header == "This module provides hooks."
    art = '"""\n+-----+\n|  *  |\n+-----+\n\nReal purpose here.\n"""\n'
    assert analyze_snippet("m.py", art).header == "Real purpose here."
    over = '"""\n=====\nTitle\n=====\n\nBody text.\n"""\n'
    assert analyze_snippet("m.py", over).header == "Body text."
    only_fields = '"""\n:copyright: (c) x\n:license: MIT\n"""\n'
    assert analyze_snippet("m.py", only_fields).header == ""


# ---------------------------------------------------------------- 5. TS value exports


def test_ts_exported_values_and_aliases():
    src = (
        "const createImpl = (s) => s\n"
        "export const createStore = ((createState) =>\n"
        "  createState ? createImpl(createState) : createImpl) as CreateStore\n"
        "export const persist = createImpl as unknown as Persist\n"
        "export const settings = { a: 1 } satisfies Settings\n"
        "export let counter = 0\n"
        "const hidden = 3\n"
        "export const MAX_SIZE = 10\n"
        "export const typed: Handler = (a, b) => a\n"
        "export const fnType: (a: number) => void = (a) => {}\n"
    )
    facts = analyze_snippet("a.ts", src)
    items = by_name(facts)
    assert "hidden" not in items and "MAX_SIZE" not in items
    assert facts.consts == ["MAX_SIZE"]
    assert (items["createStore"].kind, items["createStore"].signature) == (
        "function",
        "createStore(createState)",
    )
    assert (items["persist"].kind, items["persist"].signature) == ("function", "persist(s)")
    assert items["settings"].kind == "value" and items["counter"].kind == "value"
    assert items["typed"].signature == "typed(a, b)"
    assert items["fnType"].kind == "function" and items["fnType"].signature == "fnType(a)"
    assert all(items[n].exported for n in ("createStore", "persist", "settings", "counter"))


def test_value_kind_in_template_and_spec():
    root = Path(__file__).parent.parent
    assert "k-value" in (root / "src/repotour/templates/tour.html").read_text()
    assert "`value`" in (root / "docs/SPEC.md").read_text()


# ---------------------------------------------------------------- 6. TS overloads


def test_ts_function_and_method_overloads_collapse():
    src = (
        "export function f(a: string): X;\n"
        "export function f(a: string, b: number): Y;\n"
        "export function f(a: string, b?: number): X | Y {\n  return a\n}\n\n"
        "function g(a: number): number\nfunction g(a: string): string\n"
        "function g(a: any) {\n  return a\n}\n\n"
        "declare function h(a: number): void;\n\n"
        "class C {\n  m(a: string): X;\n  m(a: number): Y;\n"
        "  m(a: any) {\n    return a\n  }\n  other() {}\n}\n"
    )
    facts = analyze_snippet("a.ts", src)
    items = by_name(facts)
    assert names(facts.items) == ["f", "g", "h", "C"]
    assert items["f"].signature == "f(a: string, b?: number)" and items["f"].exported
    assert items["g"].signature == "g(a: any)"
    assert [(m.name, m.signature) for m in items["C"].methods] == [("m", "m(a: any)"), ("other", "other()")]


# ---------------------------------------------------------------- 7. TS multi-line signatures


def test_ts_multiline_signature_is_one_line_with_generics():
    src = "export function useStore<S, U>(\n  api: S,\n  selector: (s: S) => U,\n): U {\n  return api\n}\n"
    assert analyze_snippet("a.ts", src).items[0].signature == "useStore<S, U>(api: S, selector: (s: S) => U)"
    long = "export function f(" + ", ".join(f"argument{i}: string" for i in range(20)) + ") {}\n"
    sig = analyze_snippet("a.ts", long).items[0].signature
    assert len(sig) == 120 and sig.endswith("…")


# ---------------------------------------------------------------- 8. TS parse misses


def test_ts_generics_with_parens_and_type_predicate_returns():
    src = (
        "function getApis<Keys extends (string | undefined)[]>(\n  ...keys: Keys\n) {\n  return 1\n}\n\n"
        "const hasEntries = (\n  value: Iterable<unknown>,\n): value is Iterable<unknown> & {\n"
        "  entries(): Iterable<[unknown, unknown]>\n} =>\n  // note\n  'entries' in value\n\n"
        "type Fn<T = () => void> = T\n"
    )
    facts = analyze_snippet("a.ts", src)
    items = by_name(facts)
    assert names(facts.items) == ["getApis", "hasEntries", "Fn"]
    assert items["getApis"].signature == "getApis<Keys extends (string | undefined)[]>(...keys: Keys)"
    assert items["hasEntries"].signature == "hasEntries(value: Iterable<unknown>)"
    assert items["Fn"].signature == "type Fn<T = () => void>"


# ---------------------------------------------------------------- 9. JS/TS header


def test_js_header_skips_directives_and_tool_comments():
    src = (
        '/// <reference types="vite/client" />\n"use client"\n/* eslint-disable */\n// @ts-nocheck\n'
        "/*! Copyright 2020 Acme */\n\n// Builds the store.\n// Second line.\n\nexport const a = 1\n"
    )
    assert analyze_snippet("a.ts", src).header == "Builds the store. Second line."
    block = "'use strict';\n/**\n * Helpers for parsing.\n */\nfunction f() {}\n"
    assert analyze_snippet("a.js", block).header == "Helpers for parsing."
    assert analyze_snippet("a.js", "// prettier-ignore\n// eslint-disable-next-line\nlet x\n").header == ""


# ---------------------------------------------------------------- 10. tsconfig scoping


def test_nearest_tsconfig_wins_and_include_is_respected(tmp_path):
    files = {
        "tsconfig.json": (
            '{"compilerOptions": {"paths": {"lib": ["./src/index.ts"]}}, "include": ["src/**/*"]}'
        ),
        "src/index.ts": "",
        "src/use.ts": "",
        "examples/demo/app.jsx": "",
        "pkg/tsconfig.json": '{"extends": "../base.json", "include": ["src"]}',
        "base.json": '{"compilerOptions": {"paths": {"lib": ["./pkg/src/own.ts"]}}}',
        "pkg/src/own.ts": "",
        "pkg/src/a.ts": "",
    }
    for rel, text in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text)
    ctx = Context(root=tmp_path, files=frozenset(files))
    resolver = JsResolver(ctx)
    assert resolver.resolve("lib", "src", "src/use.ts") == "src/index.ts"
    assert resolver.resolve("lib", "examples/demo", "examples/demo/app.jsx") is None
    # nearest config (pkg/) with its extended paths, resolved against the extended file's folder
    assert resolver.resolve("lib", "pkg/src", "pkg/src/a.ts") == "pkg/src/own.ts"


# ---------------------------------------------------------------- 11. languages


def test_single_source_of_truth_for_languages():
    from repotour.analyzers import generic

    assert analyzers.DEFAULT_SUFFIXES == frozenset(analyzers.LANGUAGES)
    assert ".ts" in analyzers.DEFAULT_SUFFIXES and ".sql" in analyzers.DEFAULT_SUFFIXES
    assert not hasattr(generic, "LANGUAGES") and not hasattr(generic, "language_for")
    assert analyzers.language_for("x/a.tsx") == "typescript" and analyzers.language_for("Makefile") == "text"
    assert set(analyzers.REGISTRY) == {
        s for s, lang in analyzers.LANGUAGES.items() if lang in ("python", "javascript", "typescript")
    }
