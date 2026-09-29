# Tests for the JS/TS lexer and analyzer, on small snippets and on the ts_app fixture.
from conftest import analyze_snippet

from repotour.analyzers.jslex import lex
from repotour.config import Config
from repotour.repo import collect_facts


def test_lexer_blanks_comments_strings_templates_and_keeps_layout():
    src = "a = 'x'; // c\nb = `t ${ `in ${q}` } u`;\n/* m\nn */ c = /['\"]/g; d = a / 2;\n"
    lexed = lex(src)
    assert len(lexed.clean) == len(src)
    assert lexed.clean.count("\n") == src.count("\n")
    assert "// c" not in lexed.clean and "in" not in lexed.clean.replace("in ", "")
    assert lexed.clean.endswith("d = a / 2;\n")
    assert lexed.strings[src.index("'x'")] == "x"


def test_fake_import_in_string_and_fake_function_in_comment_are_ignored():
    src = (
        "const s = \"import x from 'y'\";\n// function ghost() {}\n"
        "/* function ghost2() {} */\nfunction real() {}\n"
    )
    facts = analyze_snippet("a.ts", src)
    assert [i.name for i in facts.items] == ["real"]
    assert facts.imports == {} and facts.libs == []


def test_outline_forms():
    src = (
        "export function a(x) {}\nexport async function b() {}\nfunction* c() {}\n"
        "export const d = (x: number): number => x;\nconst e = async () => {};\nvar f = function () {};\n"
        "export default class Box {\n  get v() { return 1 }\n  static make() {}\n  run() {}\n}\n"
        "interface I { a: string }\nexport type T = string;\nenum E { A }\nexport { c, e };\n"
        "export default function () {}\n"
    )
    facts = analyze_snippet("a.ts", src)
    by_name = {i.name: i for i in facts.items}
    assert by_name["a"].exported and by_name["b"].exported and by_name["d"].exported
    assert by_name["c"].exported and by_name["e"].exported and not by_name["f"].exported
    assert by_name["Box"].kind == "class"
    assert [m.signature for m in by_name["Box"].methods] == ["get v()", "static make()", "run()"]
    assert {n: by_name[n].kind for n in ("I", "T", "E")} == {"I": "type", "T": "type", "E": "type"}
    assert by_name["d"].signature == "d(x: number)"
    assert "default" in by_name


def test_import_forms_and_libs():
    files = ("src/util.ts", "src/lib/index.ts", "src/lib/thing.ts", "src/other.tsx")
    src = (
        "import a, { b as c, type D } from './util';\nimport * as ns from './lib';\nimport './other';\n"
        "import type { T } from './lib/thing.js';\nexport { z } from './util';\n"
        "export * from './lib/thing';\n"
        "const r = require('left-pad');\nconst l = () => import('@scope/pkg/deep');\n"
        "import fs from 'node:fs';\n"
    )
    facts = analyze_snippet("src/x.ts", src, files)
    assert facts.imports["src/util.ts"] == ["default", "b", "D", "z"]
    assert facts.imports["src/lib/index.ts"] == ["*"]
    assert facts.imports["src/lib/thing.ts"] == ["T", "*"]
    assert facts.imports["src/other.tsx"] == []
    assert facts.libs == ["@scope/pkg", "fs", "left-pad"]


def test_tsconfig_paths_alias_and_base_url(ts_app):
    repo = collect_facts(ts_app, Config())
    button = repo.facts["src/components/Button.tsx"]
    assert set(button.imports) == {
        "src/lib/strings.ts", "src/config.ts", "src/lib/index.ts", "src/lib/math.ts",
    }  # fmt: skip
    assert button.imports["src/config.ts"] == ["default", "Level"]
    assert button.libs == ["lodash", "react"]


def test_js_specifier_resolves_to_ts_file(ts_app):
    repo = collect_facts(ts_app, Config())
    assert "src/lib/math.ts" in repo.facts["src/lib/strings.ts"].imports  # imported as "./math.js"
    assert repo.facts["src/main.ts"].libs == ["@scope/pkg", "express", "fs"]


def test_ts_app_fixture_outline(ts_app):
    repo = collect_facts(ts_app, Config())
    math = repo.facts["src/lib/math.ts"]
    double = next(i for i in math.items if i.name == "double")
    assert [c.name for c in double.children] == ["_scale"]
    assert next(i for i in math.items if i.name == "triple").exported  # via `export { triple }`
    strings = repo.facts["src/lib/strings.ts"]
    assert [i.name for i in strings.items] == ["Formatter", "fakeTemplate"]  # no items from strings/comments
    assert {m.name for m in strings.items[0].methods} == {
        "constructor",
        "format",
        "create",
        "label",
        "render",
    }
    assert "fake" not in {i.name for i in strings.items}
    assert repo.facts["src/config.ts"].consts == ["API_URL", "MAX_RETRIES"]
    main = repo.facts["src/main.ts"]
    assert main.items[0].kind == "table" and main.items[0].calls == ["startServer", "stopServer"]
    page = next(i for i in repo.facts["src/components/Button.tsx"].items if i.name == "Page")
    assert page.calls == ["Button", "Helper"]


def test_reexport_only_index_gets_helper_role(ts_app):
    repo = collect_facts(ts_app, Config())
    assert repo.facts["src/lib/index.ts"].reexport_only
    assert repo.roles["src/lib/index.ts"] == "helper"
    assert repo.roles["src/components/Button.tsx"] == "face"
    assert repo.roles["src/main.ts"] == "conductor"
    assert repo.roles["tsconfig.json"] == "config"


def test_header_comment_forms():
    assert analyze_snippet("a.ts", "// One.\n// Two.\nconst a = 1;\n").header == "One. Two."
    assert (
        analyze_snippet("a.ts", "/**\n * Block header.\n * More.\n */\nconst a = 1;\n").header
        == "Block header. More."
    )
