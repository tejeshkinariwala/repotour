# JavaScript / TypeScript analyzer (js, jsx, mjs, cjs, ts, tsx, mts, cts) with no third-party parser.
# Steps: blank comments and literals (jslex), find declarations (jsoutline), read the imports from
# the cleaned text and resolve them to repo files or libraries (jsresolve).
from __future__ import annotations

import posixpath
import re

from repotour.analyzers.base import Context, FileFacts, add_import, count_lines
from repotour.analyzers.headers import slash_comment_header
from repotour.analyzers.jslex import Lexed, lex
from repotour.analyzers.jsoutline import Outliner
from repotour.analyzers.jsresolve import JsResolver, library_name

QUOTE = r"(?P<q>['\"`])"
# `import a, { b as c } from 'x'`, `import type { T } from 'x'`, `import * as ns from 'x'`
IMPORT_FROM = re.compile(
    r"\bimport\s+(?:type\s+)?(?P<clause>[\w$\s{},*]*?)\s*\bfrom\s*" + QUOTE + r"[ ]*['\"`]?;?"
)
IMPORT_SIDE_EFFECT = re.compile(r"\bimport\s*" + QUOTE)
IMPORT_DYNAMIC = re.compile(r"(?<![\w$.])import\s*\(\s*" + QUOTE)
REQUIRE = re.compile(r"(?<![\w$.])require\s*\(\s*" + QUOTE)
EXPORT_FROM = re.compile(
    r"\bexport\s+(?:type\s+)?(?P<clause>\*(?:\s*as\s+[\w$]+)?|\{[^}]*\})\s*from\s*" + QUOTE + r"[ ]*['\"`]?;?"
)


class JavaScriptAnalyzer:
    def analyze(self, path: str, text: str, ctx: Context) -> FileFacts:
        from repotour.analyzers import language_for

        lexed = lex(text)
        facts = FileFacts(path=path, lang=language_for(path), lines=count_lines(text))
        facts.header = slash_comment_header(text)
        facts.items, facts.consts = Outliner(text, lexed.clean).build()
        resolver = ctx.cache.get("js")
        if not isinstance(resolver, JsResolver):
            resolver = ctx.cache["js"] = JsResolver(ctx)
        libs: set[str] = set()
        _collect_imports(lexed, path, resolver, facts.imports, libs)
        facts.imports.pop(path, None)
        facts.libs = sorted(libs)
        facts.reexport_only = _only_reexports(lexed.clean, facts)
        return facts


def _collect_imports(
    lexed: Lexed, path: str, resolver: JsResolver, imports: dict[str, list[str]], libs: set[str]
) -> None:
    from_dir = posixpath.dirname(path)
    clean = lexed.clean
    statements = [(IMPORT_FROM, True), (EXPORT_FROM, True), (IMPORT_SIDE_EFFECT, False)]
    statements += [(IMPORT_DYNAMIC, False), (REQUIRE, False)]
    for regex, has_clause in statements:
        for m in regex.finditer(clean):
            spec = lexed.strings.get(m.start("q"))
            if not spec:
                continue
            names = _imported_names(m.group("clause")) if has_clause else []
            _record(path, spec, names, from_dir, resolver, imports, libs)


def _record(
    path: str,
    spec: str,
    names: list[str],
    from_dir: str,
    resolver: JsResolver,
    imports: dict[str, list[str]],
    libs: set[str],
) -> None:
    if "://" in spec or spec.startswith("#"):
        return
    target = resolver.resolve(spec, from_dir, path)
    if target is not None:
        add_import(imports, target, names)
    elif not resolver.is_relative(spec) and not spec.startswith(("/", "~")):
        libs.add(library_name(spec))


def _imported_names(clause: str) -> list[str]:
    """Names from an import/export clause: `{a, b as c}` -> [a, b]; default -> "default"; `*` -> "*"."""
    names: list[str] = []
    before, brace, rest = clause.partition("{")
    head = before.strip().rstrip(",").strip()
    if head.startswith("*"):
        names.append("*")
    elif head:
        names.append("default")
    if brace:
        for part in rest.rsplit("}", 1)[0].split(","):
            name = re.split(r"\s+as\s+", re.sub(r"^\s*type\s+", "", part))[0].strip()
            if name:
                names.append(name)
    return names


def _only_reexports(clean: str, facts: FileFacts) -> bool:
    """True when the file has no declarations and its only statements are re-exports and imports."""
    if facts.items or facts.consts or not EXPORT_FROM.search(clean):
        return False
    rest = EXPORT_FROM.sub("", clean)
    rest = IMPORT_FROM.sub("", rest)
    return rest.strip(" \t\r\n;") == ""
